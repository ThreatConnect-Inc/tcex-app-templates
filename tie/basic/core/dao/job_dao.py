"""Job DAO."""

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Generic, TypeVar

import arrow

from core.json_db import JsonDB, SortOrder, where
from core.json_db.dao import JsonDBDAO
from core.model.settings_model_base import SettingModelBase
from core.model.tie.job_request_base_model import JobRequestBaseModel
from model.job_request_model import JobRequestModel

if TYPE_CHECKING:
    # Note: TYPE_CHECKING import to avoid circular import at runtime.
    # TaskPathPipeABC imports JobRequestDAO, so we can't import it directly here.
    from core.task.task_path_pipe_abc import TaskPathPipeABC

M = TypeVar('M', bound=JobRequestBaseModel)


class JobRequestDAO(JsonDBDAO[M], Generic[M]):
    """Job Request DAO"""

    def __init__(
        self, db: JsonDB, settings: SettingModelBase, model: type[M] = JobRequestModel
    ) -> None:
        """."""
        super().__init__(db, model)
        self.settings = settings

    def get_all_job_ids(self) -> list[str]:
        """Get all job IDs."""
        return [self.db.get_index_from_path(path) for path in self.db.get_paths(self.model)]

    def get_jobs_over_limit(self, max_jobs: int) -> Iterable[M]:
        """Get jobs over the limit."""
        paths = self.db.get_paths(self.model, sort_by='index', sort_order='desc')
        paths = paths[max_jobs:]
        for path in paths:
            job = self.db.load_from_path(self.model, path)
            if job is not None:
                yield job

    def get_jobs_to_clean(self, max_jobs: int) -> Iterable[M]:
        """Get jobs over the limit."""
        hits = 0
        preserved_pipelines: set[str | None] = set()
        # this iterates over the jobs with the most recent job first
        for job in self.db.load_all(self.model, sort_by='index', sort_order='desc'):
            # if the job is not completed or failed do NOT clean it
            if not job.date_completed and not job.date_failed:
                continue
            # do not clean jobs that are actively retrying
            if job.status.casefold() == self.settings.job.status_retry_pending.casefold():
                continue
            # We do not want to clean the most recent scheduled job per pipeline
            if job.job_type == 'scheduled' and job.pipeline not in preserved_pipelines:
                preserved_pipelines.add(job.pipeline)
                continue
            hits += 1
            # if we have hit the limit, yield the job
            if hits > max_jobs:
                yield job

    def get_completed_before(self, before: arrow.Arrow) -> Iterable[M]:
        """Get completed jobs before a date."""
        for job in self.db.load_all(self.model):
            done_date = job.date_completed or job.date_failed
            if done_date is not None and done_date < before:
                yield job

    def get_next_for_task(self, task: 'TaskPathPipeABC') -> M | None:  # noqa: C901
        """Get the next job for the pipeline, respecting per-job backoff.

        Priority order:
        1. Jobs ready for retry (backoff expired) - highest priority
        2. Normal scheduled jobs (no backoff)
        3. Ad-hoc jobs (lowest priority)

        Jobs still in backoff (retry_after > now) are skipped.
        """
        now = datetime.now(UTC)
        job_paths = self.db.get_paths(self.model, sort_by='index', sort_order='asc') or []

        retry_candidate = None  # Job ready for retry (highest priority)
        normal_candidate = None  # Normal pending job
        ad_hoc_candidate = None  # Ad-hoc job (lowest priority)

        for job_path in job_paths:
            job = self.db.load_from_path(self.model, job_path)
            if job is None:
                continue

            # Filter by status (pending or active for this task)
            if not self._is_eligible_status(job, task):
                continue

            # Filter by pipeline
            if task.pipeline and job.pipeline != task.pipeline:
                continue

            # Check backoff state
            if job.retry_after is not None:
                if job.is_in_backoff(now):
                    continue
                # Backoff expired - this is a retry candidate (high priority)
                if retry_candidate is None:
                    retry_candidate = job
                continue

            # Normal job (no backoff state)
            # Use job_type field instead of isinstance since jobs are loaded as JobRequestModel
            if job.job_type == 'ad-hoc':
                if ad_hoc_candidate is None:
                    ad_hoc_candidate = job
            elif normal_candidate is None:
                normal_candidate = job

        # Priority: retry > scheduled > ad-hoc
        return retry_candidate or normal_candidate or ad_hoc_candidate

    def _is_eligible_status(self, job: JobRequestModel, task: 'TaskPathPipeABC') -> bool:
        """Check if job status is eligible for this task."""
        status_lower = job.status.casefold()
        return (
            status_lower == self.settings.job.status_pending.casefold()
            or status_lower == self.settings.job.status_retry_pending.casefold()
            or status_lower == task.task_settings.status_active.casefold()
        )

    def get_last_run_job(self, request_id, pipeline: str | None = None) -> M | None:
        """Get the last run job."""
        for j in self.db.load_all(
            self.model,
            where=where.where({'job_type': where.eq('scheduled')}),
            sort_order=SortOrder.DESC,
        ):
            if pipeline and j.pipeline != pipeline:
                continue
            if j.request_id == request_id:
                continue
            return j

        return None

    def get_most_recent_scheduled_job(self, pipeline: str | None = None) -> M | None:
        """Get the most recent scheduled job."""
        for j in self.db.load_all(
            self.model,
            where=where.where({'job_type': where.eq('scheduled')}),
            sort_order=SortOrder.DESC,
        ):
            if pipeline and j.pipeline != pipeline:
                continue
            return j

        return None

    def get_last_completed_job_time(self, pipeline: str) -> datetime | None:
        """Get the most recent job completion time for a pipeline.

        Used by Supervisor for staleness detection - if no job has fully completed
        (entire pipeline: download → convert → upload) within threshold, trigger shutdown.

        Uses date_completed, NOT date_download_complete, because we want to know
        if the app is successfully processing jobs end-to-end.
        """
        for job in self.db.load_all(
            JobRequestModel,
            where=where.where(
                {
                    'pipeline': where.eq(pipeline),
                    'job_type': where.eq('scheduled'),
                }
            ),
            sort_order=SortOrder.DESC,
        ):
            if job.date_completed is not None:
                return job.date_completed
        return None

    def get_first_job_time(self, pipeline: str) -> datetime | None:
        """Get the earliest job queue time for a pipeline.

        Used by Supervisor as fallback baseline for staleness detection when no
        jobs have completed yet. Measures "time since we started trying to process
        this pipeline."
        """
        earliest: datetime | None = None
        for job in self.db.load_all(
            JobRequestModel,
            where=where.where(
                {
                    'pipeline': where.eq(pipeline),
                    'job_type': where.eq('scheduled'),
                }
            ),
        ):
            if earliest is None or job.date_queued < earliest:
                earliest = job.date_queued
        return earliest

    def get_known_pipelines(self) -> set[str]:
        """Get all pipeline names that have jobs."""
        pipelines = set()
        for job in self.db.load_all(JobRequestModel):
            if job.pipeline:
                pipelines.add(job.pipeline)
        return pipelines

    def is_pipeline_in_upload_stage(self, pipeline: str) -> bool:
        """Check if any job in this pipeline is currently in the upload stage.

        Upload stage is detected by job status starting with "upload" and containing "in progress".
        This is used by Supervisor to skip staleness checks for pipelines actively uploading.
        """
        for job in self.db.load_all(
            JobRequestModel,
            where=where.where({'pipeline': where.eq(pipeline)}),
        ):
            status_lower = job.status.casefold()
            if status_lower.startswith('upload') and 'in progress' in status_lower:
                return True
        return False
