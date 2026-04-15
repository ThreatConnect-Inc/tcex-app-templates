"""Class for /api/job/{job_id}/retry endpoint - manage job status transitions.

This endpoint allows manual intervention to move jobs between pipeline stages.

Example API calls:
    # Get available stages for a job
    GET /api/job/{job_id}/retry
    Response: {"stages": ["pending", "download", "convert", "upload"], ...}

    # Retry a failed job at upload stage
    POST /api/job/{job_id}/retry
    {"target_stage": "upload"}

    # Reset job to beginning of pipeline (will re-download)
    POST /api/job/{job_id}/retry
    {"target_stage": "pending"}

    # Move to convert stage without clearing backoff timer
    POST /api/job/{job_id}/retry
    {"target_stage": "convert", "clear_backoff": false}

    # Update status only, don't move files
    POST /api/job/{job_id}/retry
    {"target_stage": "upload", "move_files": false}
"""

import re
from functools import cached_property

import falcon
from pydantic import BaseModel, Field, field_validator
from spectree import Response

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_job
from core.api.validation.models import QueryParamModel
from core.dao.job_dao import JobRequestDAO


class JobStatusUpdateRequest(BaseModel):
    """Request body for updating job status.

    Example:
        {"target_stage": "upload", "clear_backoff": true, "move_files": true}
    """

    target_stage: str = Field(
        ...,
        description='Target stage (task name) to move the job to.',
    )
    clear_backoff: bool = Field(
        default=True,
        description='Clear retry_after to allow immediate processing.',
    )
    move_files: bool = Field(
        default=True,
        description='Attempt to move job files to the target working directory.',
    )

    @field_validator('target_stage')
    @classmethod
    def _validate_target_stage(cls, v):
        """Validate target_stage contains only safe characters (prevent path traversal)."""
        if not re.match(r'^[a-zA-Z0-9_\- ]+$', v):
            raise ValueError(
                'target_stage must contain only alphanumeric characters, '
                'underscores, hyphens, and spaces'
            )
        return v.strip()


class JobRetryResource(EndpointBase):
    """Manage job status transitions - move jobs between pipeline stages."""

    @cached_property
    def dao(self) -> JobRequestDAO:
        """Return the dao."""
        return JobRequestDAO(self.db, self.settings)

    def _get_stages_for_pipeline(self, pipeline: str | None) -> list[dict]:
        """Get available stages for a pipeline from registered tasks.

        Returns list of stage info dicts with name, status, and working_dir.
        Always includes 'pending' as first option.
        """
        stages = [
            {
                'name': 'pending',
                'status': 'Pending',
                'working_dir': None,
                'order': 0,
            }
        ]

        if not self.tasks:
            return stages

        # Get tasks for this pipeline (or all tasks if no pipeline specified)
        for task in self.tasks.all():
            task_pipeline = getattr(task, 'pipeline', None)

            # Include task if it matches the pipeline or has no pipeline set
            if pipeline is None or task_pipeline is None or task_pipeline == pipeline:
                task_settings = getattr(task, 'task_settings', None)
                if task_settings:
                    name = getattr(task_settings, 'name', None)
                    if not name:
                        continue
                    fallback = name.lower().replace(' ', '_')
                    name_camel = getattr(task_settings, 'name_camel', fallback)
                    stages.append(
                        {
                            'name': name.lower(),
                            'status': f'{name} In Progress',
                            'working_dir': f'{name_camel}_working_dir',
                            'order': getattr(task_settings, 'index', len(stages)) + 1,
                        }
                    )

        # Sort by order and deduplicate by name
        seen = set()
        unique_stages = []
        for stage in sorted(stages, key=lambda s: s['order']):
            if stage['name'] not in seen:
                seen.add(stage['name'])
                unique_stages.append(stage)

        return unique_stages

    def _derive_stage_config(self, stage_name: str) -> tuple[str, str | None]:
        """Derive status and working directory from stage name.

        Uses convention: stage "foo" -> status "Foo In Progress", dir "foo_working_dir"

        Returns:
            Tuple of (display_status, working_dir_name)
        """
        stage_lower = stage_name.lower().strip()

        if stage_lower == 'pending':
            return 'Pending', None

        # Title case each word for status
        status = f'{stage_lower.title()} In Progress'
        working_dir = f'{stage_lower}_working_dir'

        return status, working_dir

    def _move_job_files(self, job_id: str, target_dir_name: str) -> tuple[bool, str | None]:
        """Search for and move job files to target directory.

        Returns:
            Tuple of (files_moved, source_directory_path)
        """
        target_dir = self.settings.base_path / target_dir_name
        target_dir.mkdir(parents=True, exist_ok=True)

        # Search all *_working_dir directories
        for search_dir in self.settings.base_path.glob('*_working_dir'):
            if not search_dir.is_dir() or search_dir.name == target_dir_name:
                continue

            for path in search_dir.glob(f'*#{job_id}'):
                if path.is_dir():
                    dest_path = target_dir / path.name
                    self.log.info(
                        f'event=move-job-files, job_id={job_id}, '
                        f'source={path}, destination={dest_path}'
                    )
                    path.rename(dest_path)
                    return True, str(search_dir)

        return False, None

    @spec.validate(
        resp=Response('HTTP_200'),
        query=QueryParamModel,
        skip_validation=True,
        tags=[tag_job],
    )
    def on_get(
        self,
        req: FalconRequest,  # noqa: ARG002
        resp: FalconResponse,
        query_params: QueryParamModel,  # noqa: ARG002
        job_id: str,
    ):
        """Return available stages for moving this job.

        Response includes:
        - job_id: The job ID
        - pipeline: The job's pipeline
        - current_status: Current job status
        - stages: List of available target stages with name, status, working_dir
        """
        # Get the job
        try:
            job = self.dao.get(job_id)
        except FileNotFoundError as e:
            raise falcon.HTTPNotFound(
                title='Not Found', description=f'Job {job_id} not found.'
            ) from e

        stages = self._get_stages_for_pipeline(job.pipeline)

        resp.media = {
            'job_id': job_id,
            'pipeline': job.pipeline,
            'current_status': job.status,
            'stages': stages,
        }
        resp.status = falcon.HTTP_200

    @spec.validate(
        resp=Response('HTTP_200'),
        query=QueryParamModel,
        skip_validation=True,
        tags=[tag_job],
    )
    def on_post(
        self,
        req: FalconRequest,
        resp: FalconResponse,
        query_params: QueryParamModel,  # noqa: ARG002
        job_id: str,
    ):
        """Update job status and optionally move files to target stage."""
        # Parse request body
        try:
            body = req.media or {}
            request = JobStatusUpdateRequest(**body)
        except Exception as e:
            raise falcon.HTTPBadRequest(
                title='Bad Request',
                description=f'Invalid request body: {e}',
            ) from e

        # Get the job
        try:
            job = self.dao.get(job_id)
        except FileNotFoundError as e:
            raise falcon.HTTPNotFound(
                title='Not Found', description=f'Job {job_id} not found.'
            ) from e

        old_status = job.status
        pipeline = job.pipeline

        # Look up stage info from registered tasks (preferred) or derive from name (fallback)
        target_status = None
        target_dir_name = None
        stages = self._get_stages_for_pipeline(pipeline)
        for stage in stages:
            if stage['name'].lower() == request.target_stage.lower():
                target_status = stage['status']
                target_dir_name = stage['working_dir']
                break

        # Fallback to deriving from stage name if not found in registered tasks
        if target_status is None:
            target_status, target_dir_name = self._derive_stage_config(request.target_stage)

        # Move files if requested and target has a working directory
        files_moved = False
        source_dir = None
        if request.move_files and target_dir_name:
            files_moved, source_dir = self._move_job_files(job_id, target_dir_name)

        # Update job status
        job.status = target_status
        if request.clear_backoff:
            job.retry_after = None

        # Clear retry state when resetting to pending (fresh start)
        if target_status.casefold() == self.settings.job.status_pending.casefold():
            job.failure_count = 0
            job.retry_after = None
            job.date_failed = None

        self.dao.save(job)

        self.log.info(
            f'event=job-status-updated, job_id={job_id}, pipeline={pipeline}, '
            f'old_status={old_status}, new_status={job.status}, files_moved={files_moved}'
        )

        resp.media = {
            'message': f'Job {job_id} status updated.',
            'job_id': job_id,
            'pipeline': pipeline,
            'old_status': old_status,
            'new_status': job.status,
            'target_stage': request.target_stage,
            'files_moved': files_moved,
            'source_directory': source_dir,
        }
        resp.status = falcon.HTTP_200
