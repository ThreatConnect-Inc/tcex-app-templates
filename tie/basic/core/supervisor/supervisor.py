"""Supervisor - Tracks pipeline health and triggers shutdown on staleness."""

import logging
import random
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from core.supervisor.config import SupervisorConfigModel

if TYPE_CHECKING:
    from core.dao.job_dao import JobRequestDAO
    from core.json_db import JsonDB
    from core.model.settings_model_base import SettingModelBase
    from tcex.exit.exit import Exit

logger = logging.getLogger('tcex')


class Supervisor:
    """Tracks pipeline health and triggers shutdown on staleness.

    Key responsibilities:
    - Tracks per-pipeline health via job completion times (using job_dao)
    - Provides tick() for periodic health checks
    - Triggers shutdown if ANY pipeline has had no completed jobs for threshold
    - Provides compute_backoff() for per-job backoff calculation

    Per-job backoff is tracked on JobRequestModel fields (retry_after, failure_count).
    Job selection with backoff is handled by JobRequestDAO.get_next_for_task().

    Shutdown behavior:
    - Pipeline staleness (no completed jobs for threshold): triggers shutdown
    - Individual job failures: handled per-job with backoff (no shutdown)
    """

    def __init__(
        self,
        db: 'JsonDB',
        job_dao: 'JobRequestDAO',
        settings: 'SettingModelBase',
        exit_service: 'Exit | None' = None,
    ):
        """Initialize Supervisor.

        Args:
            db: JsonDB instance for persisting config.
            job_dao: JobRequestDAO for querying job completion times.
            settings: Application settings containing failure threshold.
            exit_service: Exit service for triggering shutdown on staleness.
        """
        self.db = db
        self.job_dao = job_dao
        self.settings = settings
        self.log = logger
        self.exit_service = exit_service

        # Shutdown state (checked by watchdog for graceful shutdown)
        self._shutdown_requested = False
        self._shutdown_reason: str | None = None

        # Load or create config (for backoff settings)
        self._config = self._load_or_create_config()

    def _load_or_create_config(self) -> SupervisorConfigModel:
        """Load existing config from JsonDB or create with defaults."""
        try:
            return self.db.load(SupervisorConfigModel, 'supervisor_config')
        except FileNotFoundError:
            config = SupervisorConfigModel()
            self.db.save(config)
            return config
        except Exception:
            self.log.exception('supervisor-event=load-config-failed')
            return SupervisorConfigModel()

    @property
    def config(self) -> SupervisorConfigModel:
        """Return the current config model (for API access)."""
        return self._config

    def reload_config(self) -> None:
        """Reload config from JsonDB. Call after API updates."""
        self._config = self._load_or_create_config()
        self.log.info('supervisor-event=config-reloaded')

    def tick(self) -> None:
        """Check for stale pipelines and trigger shutdown if needed.

        For each pipeline, computes an "effective baseline" using (in priority order):
        1. last_completed - most recent job completion (from job history)
        2. pipeline_baseline - manual API reset
        3. first_job_time - when pipeline first had a job queued

        If time since effective baseline exceeds threshold, triggers shutdown.

        Note: Pipelines on probation are skipped - they have their own shutdown logic
        (probation job failure triggers immediate shutdown).

        Note: Pipelines in upload stage are skipped - upload manages its own retry lifecycle.
        See UPLOAD_RETRY_REDESIGN_PLAN.md for rationale.
        """
        threshold = self.settings.advanced_settings.failure_threshold
        now = datetime.now(UTC)

        for pipeline in self.job_dao.get_known_pipelines():
            # Skip pipelines on probation - they have separate shutdown logic
            if self.is_pipeline_on_probation(pipeline):
                continue

            # Skip pipelines in upload stage - upload manages its own retry lifecycle
            # Data is good at this point; upload just needs time to push
            if self.job_dao.is_pipeline_in_upload_stage(pipeline):
                self.log.debug(f'supervisor-event=skip-staleness-upload-stage, pipeline={pipeline}')
                continue

            effective_baseline = self._get_effective_baseline(pipeline)

            if effective_baseline is None:
                # Defensive: shouldn't happen for known pipelines
                continue

            time_since_baseline = now - effective_baseline
            if time_since_baseline > threshold:
                self._trigger_shutdown(pipeline, effective_baseline, time_since_baseline)

    def _get_effective_baseline(self, pipeline: str) -> datetime | None:
        """Get the effective health baseline for a pipeline.

        Priority:
        1. last_completed - most recent job completion (from job history)
        2. pipeline_baseline - manual API reset (overrides staleness timer)
        3. first_job_time - when pipeline started (fallback for new pipelines)

        Returns the most recent of (1) and (2), or falls back to (3).
        """
        last_completed = self.job_dao.get_last_completed_job_time(pipeline)
        baseline_reset = self._config.pipeline_baseline.get(pipeline)

        # Use max of last_completed and manual reset (if either exists)
        candidates = [t for t in [last_completed, baseline_reset] if t is not None]
        if candidates:
            return max(candidates)

        # Fallback: use first job queue time (when we started trying)
        return self.job_dao.get_first_job_time(pipeline)

    def reset_pipeline_baseline(self, pipelines: list[str] | None = None) -> dict[str, datetime]:
        """Reset the health baseline for specified pipelines or all known pipelines.

        Sets pipeline_baseline to now, which acts as an alternative to last_completed
        for staleness detection. Also clears any probation status for the pipelines.
        Useful for:
        - Manual recovery after fixing an issue
        - API-triggered reset

        Args:
            pipelines: List of pipeline names to reset. If None/empty, resets all.

        Returns:
            Dict of pipeline_name -> reset timestamp for each pipeline that was reset.
        """
        now = datetime.now(UTC)
        reset_pipelines = pipelines if pipelines else list(self.job_dao.get_known_pipelines())

        reset_times = {}
        cleared_probation = []
        for pipeline in reset_pipelines:
            self._config.pipeline_baseline[pipeline] = now
            reset_times[pipeline] = now
            # Also clear probation if set
            if pipeline in self._config.pipelines_on_probation:
                del self._config.pipelines_on_probation[pipeline]
                cleared_probation.append(pipeline)

        if reset_times:
            self.db.save(self._config)
            self.log.info(
                f'supervisor-event=pipeline-baseline-reset, pipelines={list(reset_times.keys())}'
            )
            if cleared_probation:
                self.log.info(
                    f'supervisor-event=probation-cleared-by-reset, pipelines={cleared_probation}'
                )

        return reset_times

    # -------------------------------------------------------------------------
    # Probation Mode Methods
    # -------------------------------------------------------------------------

    def check_and_enter_probation(self) -> dict[str, bool]:
        """Check for stale pipelines on startup and enter probation mode.

        Called on app startup. For each pipeline:
        - If healthy (not stale): no action needed
        - If stale: enter probation mode (first job must succeed or app shuts down)

        Staleness is determined by last_job_completed (from job history). We do NOT
        touch pipeline_baseline here - that's only for manual API resets.

        When a probation job completes successfully, it sets date_completed on the job,
        which automatically updates last_job_completed, clearing the staleness.

        Returns:
            Dict of pipeline_name -> is_on_probation for each pipeline.
        """
        threshold = self.settings.advanced_settings.failure_threshold
        now = datetime.now(UTC)
        results = {}

        for pipeline in self.job_dao.get_known_pipelines():
            effective_baseline = self._get_effective_baseline(pipeline)

            if effective_baseline is None:
                # Defensive: shouldn't happen for known pipelines (they have jobs with date_queued)
                self.log.warning(f'supervisor-event=no-baseline-for-pipeline, pipeline={pipeline}')
                continue

            time_since_baseline = now - effective_baseline
            if time_since_baseline > threshold:
                # Pipeline is stale - enter probation mode
                self._config.pipelines_on_probation[pipeline] = ''  # Awaiting job assignment
                results[pipeline] = True
                self.log.warning(
                    f'supervisor-event=entering-probation, '
                    f'pipeline={pipeline}, '
                    f'time_since_baseline={time_since_baseline}, '
                    f'threshold={self.settings.advanced_settings.failure_threshold}'
                )
            else:
                # Pipeline is healthy - no action needed
                results[pipeline] = False
                self.log.info(f'supervisor-event=startup-healthy-pipeline, pipeline={pipeline}')

        # Only save if we made changes (entered probation)
        if any(results.values()):
            self.db.save(self._config)
        return results

    def is_pipeline_on_probation(self, pipeline: str) -> bool:
        """Check if a pipeline is currently on probation."""
        return pipeline in self._config.pipelines_on_probation

    def get_probation_job_id(self, pipeline: str) -> str | None:
        """Get the probation job ID for a pipeline, or None if not on probation or awaiting."""
        value = self._config.pipelines_on_probation.get(pipeline)
        return value if value else None

    def set_probation_job(self, pipeline: str, request_id: str) -> bool:
        """Assign a job as the probation job for a pipeline.

        Only assigns if the pipeline is on probation and awaiting job assignment (value is None).

        Args:
            pipeline: The pipeline name.
            request_id: The job request ID to assign as probation job.

        Returns:
            True if the job was assigned as probation job, False otherwise.
        """
        if pipeline not in self._config.pipelines_on_probation:
            return False

        if self._config.pipelines_on_probation[pipeline] != '':
            # Already has a probation job assigned
            return False

        self._config.pipelines_on_probation[pipeline] = request_id
        self.db.save(self._config)
        self.log.info(
            f'supervisor-event=probation-job-assigned, pipeline={pipeline}, request_id={request_id}'
        )
        return True

    def is_probation_job(self, pipeline: str, request_id: str) -> bool:
        """Check if a specific job is the probation job for a pipeline."""
        return self._config.pipelines_on_probation.get(pipeline) == request_id

    def clear_probation(self, pipeline: str) -> bool:
        """Clear probation status for a pipeline after successful completion.

        Args:
            pipeline: The pipeline name.

        Returns:
            True if probation was cleared, False if pipeline wasn't on probation.
        """
        if pipeline not in self._config.pipelines_on_probation:
            return False

        del self._config.pipelines_on_probation[pipeline]
        self.db.save(self._config)
        self.log.info(f'supervisor-event=probation-cleared, pipeline={pipeline}')
        return True

    @property
    def shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_requested

    @property
    def shutdown_reason(self) -> str | None:
        """Get the reason for shutdown request."""
        return self._shutdown_reason

    def request_shutdown(self, reason: str) -> None:
        """Request graceful shutdown. Watchdog will handle actual exit.

        Args:
            reason: Human-readable reason for shutdown.
        """
        self._shutdown_requested = True
        self._shutdown_reason = reason
        self.log.error(f'supervisor-event=shutdown-requested, reason={reason}')

    def trigger_probation_failure(self, pipeline: str, request_id: str) -> None:
        """Signal shutdown due to probation job failure.

        Note: This may be called from a forked process. The task should also
        set ns.unrecoverable_failure=True for cross-process signaling.
        Watchdog will handle graceful shutdown.

        Args:
            pipeline: The pipeline name.
            request_id: The failed job request ID.
        """
        self.log.error(
            f'supervisor-event=probation-failure-shutdown, '
            f'pipeline={pipeline}, '
            f'request_id={request_id}'
        )

        reason = (
            f'Probation job "{request_id}" for pipeline "{pipeline}" failed. '
            f'Pipeline was stale on startup and first job did not succeed.'
        )
        self.request_shutdown(reason)

    def _trigger_shutdown(
        self, pipeline: str, last_completed: datetime, duration: timedelta
    ) -> None:
        """Signal shutdown due to pipeline staleness.

        Called from tick() in the main process. Watchdog will handle graceful shutdown.
        """
        self.log.error(
            f'supervisor-event=staleness-shutdown, '
            f'pipeline={pipeline}, '
            f'last_completed={last_completed.isoformat()}, '
            f'duration={duration}, '
            f'threshold={self.settings.advanced_settings.failure_threshold}'
        )

        reason = (
            f'Pipeline "{pipeline}" has had no completed jobs '
            f'for {duration} (threshold: {self.settings.advanced_settings.failure_threshold}).'
        )
        self.request_shutdown(reason)

    def compute_backoff(self, failure_count: int) -> timedelta:
        """Compute backoff duration for a given failure count.

        Used by task error handlers to set retry_after on jobs.

        Args:
            failure_count: Number of consecutive failures.

        Returns:
            Backoff duration as timedelta.
        """
        # Exponential backoff: base * 2^(failures-1)
        multiplier = 2 ** (failure_count - 1)
        seconds = self._config.backoff_base_seconds * multiplier

        # Cap at maximum
        seconds = min(seconds, self._config.backoff_max_seconds)

        # Add jitter (+/-jitter%)
        jitter_range = seconds * self._config.backoff_jitter
        jitter = random.uniform(-jitter_range, jitter_range)  # nosec B311
        seconds = max(0, seconds + jitter)

        return timedelta(seconds=seconds)

    def get_pipeline_health(self) -> dict[str, Any]:
        """Return pipeline health status for API.

        Returns a simplified view with single 'last_completed' timestamp per pipeline.
        This is the effective baseline: max(job_history_completion, manual_api_override).
        """
        now = datetime.now(UTC)
        threshold = self.settings.advanced_settings.failure_threshold
        health = {}

        for pipeline in self.job_dao.get_known_pipelines():
            last_completed = self._get_effective_baseline(pipeline)
            time_since = (now - last_completed).total_seconds() if last_completed else None

            health[pipeline] = {
                'last_completed': (last_completed.isoformat() if last_completed else None),
                'is_stale': (time_since > threshold.total_seconds() if time_since else False),
                'threshold': str(self.settings.advanced_settings.failure_threshold),
            }

        return health

    def get_status(self) -> dict[str, Any]:
        """Return status for API.

        Returns:
            Dictionary containing pipeline health and config.
        """
        return {
            'config': self._config.dict(),
            'pipeline_health': self.get_pipeline_health(),
        }
