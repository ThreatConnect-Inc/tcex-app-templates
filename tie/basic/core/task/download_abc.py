"""Task Module"""

import contextlib
import shutil
from abc import abstractmethod
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

from tcex import TcEx

from core.json_db import JsonDB

# from more import Metrics
from core.model.tie.job_request_base_model import JobRequestBaseModel
from core.service.metrics import Metrics
from core.service.writing_service import WritingModel, WritingService
from core.task.task_path_pipe_abc import TaskPathPipeABC, UnrecoverableError
from core.task.tasks import Tasks
from model import AdHocJobRequestModel
from model.settings_model import SettingModel
from sdk.sdk import SDK

T = TypeVar('T', bound=JobRequestBaseModel)


class DownloadABC(TaskPathPipeABC):
    """Task Module"""

    def __init__(
        self,
        settings: SettingModel,
        tcex: TcEx,
        db: JsonDB,
        *,
        sdk=None,
        pipeline=None,
        request_schema: type[T] = JobRequestBaseModel,
    ):
        """Initialize class properties."""
        super().__init__(settings, tcex, db, request_schema=request_schema)

        self.log.info('action="initialize", message="Initializing Download class"')

        # properties
        self.sdk: SDK = sdk
        self.pipeline = pipeline
        self.metrics = None
        self.writing_service = WritingService(self.db, self.log)
        self.preflight_checks = [self._is_throttled_preflight_check]

    def process_group(self, item, chunk, writer: WritingModel):
        """Process item."""
        chunk.append(item)
        self.update_heartbeat(verbose=False)
        return self.writing_service.write_groups(chunk, writer)

    def process_indicator(self, item, chunk, writer: WritingModel):
        """Process item."""
        chunk.append(item)
        self.update_heartbeat(verbose=False)
        return self.writing_service.write_indicators(chunk, writer)

    def _is_throttled_preflight_check(self):
        if self._throttle_download():
            self.log.trace(
                f'task-event=launch-preflight-check-skip, action={self.task_settings.name}, '
                f'reason=throttle-limit-hit, throttle-limit={self.settings.job.throttle_limit}'
            )
            return True
        return False

    def register_preflight_check(self, check: Callable[[], bool]):
        """Register preflight check."""
        self.preflight_checks.append(check)

    def launch_preflight_checks(self):
        """Launch preflight checks."""
        try:
            if self.ns.unrecoverable_failure is True:
                return
            next_job = self.job_dao.get_next_for_task(self)
            if not next_job:
                return
            if next_job.pipeline != self.pipeline:
                return

            for check in self.preflight_checks:
                if check() is True:
                    return
        except Exception:
            self.log.exception('task-event=launch-preflight-check-error')
            return
        self.metrics = Metrics(self.db)
        self.launch(request_id=next_job.request_id)

    def run(self, request_id: str, input_dir: Path, output_dir: Path):  # noqa: ARG002
        """Run the task."""
        self.log.info(f'action="run-task", message="Running the task for request-id={request_id}"')

        request = self.job_dao.get(request_id)
        self.writing_service.request = request

        # If pipeline is on probation and awaiting first job, assign this job as probation job
        if self.pipeline and self.supervisor.is_pipeline_on_probation(self.pipeline):
            self.supervisor.set_probation_job(self.pipeline, request_id)

        # reset the download counts
        request.count_download_group = 0
        request.count_download_indicator = 0
        self.job_dao.save(request)
        self.writing_service.request = request

        self.download(output_dir, request)
        self.metrics.process_metrics()
        self.log.info('action="task-complete", message="Task completed successfully"')

    @abstractmethod
    def download(self, output_dir: Path, request):
        """Download resources from provider."""

    def _throttle_download(self) -> bool:
        """Throttle download to prevent to much stale data on disk."""
        throttle_statutes = [
            self.settings.job.status_cancelled,
            self.settings.job.status_failed,
            self.settings.job.status_pending,
            self.settings.job.status_retry_pending,
        ]
        throttle_statutes.extend(Tasks.status_final)
        # TODO fix this to account for different pipes
        running_tasks = [
            r for r in self.job_dao.get_all() if r.status.lower() not in throttle_statutes
        ]
        self.log.trace(
            f'task-event=throttle-download, count={len(running_tasks)}'
            f' final-status={Tasks.status_final}'
        )
        if len(running_tasks) >= self.settings.job.throttle_limit:
            return True
        return False

    def handle_run_error(
        self, request_id: str, request_dir: Path, exception: Exception | None = None
    ):
        """Handle download errors with per-job backoff.

        UnrecoverableError: Fail immediately and shutdown (config errors, bad credentials)
        Ad-hoc jobs: Fail immediately (existing behavior)
        Scheduled jobs: Enter backoff/retry logic with threshold
        Probation jobs: Trigger immediate shutdown (pipeline was stale on startup)
        """
        job = self.job_dao.get(request_id)

        # Unrecoverable errors always trigger immediate shutdown
        if isinstance(exception, UnrecoverableError):
            self.log.error(f'Unrecoverable error for job {request_id}: {exception}')
            job.status = self.settings.job.status_failed
            job.date_failed = datetime.now(UTC)
            self.job_dao.save(job)

            self.ns.unrecoverable_failure = True
            return

        # Ad-hoc jobs fail immediately - no backoff/retry (existing behavior)
        if isinstance(job, AdHocJobRequestModel):
            self._task_set_status(
                request_id,
                self.settings.job.status_failed,
                ['date_failed'],
            )
            return

        # Check if this is a probation job - if so, trigger shutdown
        if self.pipeline and self.supervisor.is_probation_job(self.pipeline, request_id):
            # Mark job as failed before triggering shutdown
            job.status = self.settings.job.status_failed
            job.date_failed = datetime.now(UTC)
            self.job_dao.save(job)

            self.ns.unrecoverable_failure = True
            self.supervisor.trigger_probation_failure(self.pipeline, request_id)
            return

        # Scheduled jobs: apply backoff/retry logic
        now = datetime.now(UTC)
        max_retries = self.settings.advanced_settings.max_retries

        # Track failure timestamp for logging/debugging
        if job.date_failed is None:
            job.date_failed = now

        job.failure_count += 1
        job.total_retry_count += 1  # Track total retries (never resets)

        # Check if job has exceeded max retries
        if job.failure_count >= max_retries:
            # Mark job as permanently failed
            self._mark_job_failed(job, request_dir)
            return

        # Compute backoff and schedule retry
        backoff = self.supervisor.compute_backoff(job.failure_count)
        job.retry_after = now + backoff

        # Keep status as retry pending (not failed) so it can be retried
        job.status = self.settings.job.status_retry_pending
        self.job_dao.save(job)

        self.log.warning(
            f'task-event=download-failure-backoff, '
            f'request_id={request_id}, '
            f'failure_count={job.failure_count}, '
            f'retry_after={job.retry_after}, '
            f'failing_since={job.date_failed}'
        )

    def _mark_job_failed(self, job, request_dir: Path):
        """Mark job as permanently failed after threshold exceeded."""
        job.status = self.settings.job.status_failed
        # date_failed already set, don't overwrite (preserves original failure time)
        job.retry_after = None  # No more retries
        self.job_dao.save(job)

        self.log.error(
            f'task-event=job-failed-permanently, '
            f'request_id={job.request_id}, '
            f'failure_duration={datetime.now(UTC) - job.date_failed}'
        )

        # Move to failed directory with error handling
        try:
            shutil.move(str(request_dir), self.task_settings.failed_working_dir)
        except OSError:
            self.log.exception(
                f'task-event=move-to-failed-dir-error, '
                f'request_id={job.request_id}, '
                f'source={request_dir}, '
                f'destination={self.task_settings.failed_working_dir}'
            )
            # Attempt cleanup if move failed - don't leave partial state
            with contextlib.suppress(Exception):
                shutil.rmtree(str(request_dir), ignore_errors=True)
