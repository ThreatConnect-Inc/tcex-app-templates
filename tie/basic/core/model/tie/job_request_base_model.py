"""Model Definition"""

from datetime import UTC, datetime
from typing import Any

import arrow
from pydantic import ConfigDict, Field, field_serializer, field_validator, model_validator

from core.json_db import Index
from core.model.model_base import ModelBase


class JobRequestBaseModel(ModelBase):
    """Model Definition"""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra='allow',
        from_attributes=True,
    )

    job_type: str = 'scheduled'
    date_completed: datetime | None = Field(None, description='')
    date_failed: datetime | None = Field(None, description='')
    date_queued: datetime = Field(..., description='')
    date_started: datetime | None = Field(None, description='')
    date_upload_failure: datetime | None = Field(None, description='')
    request_id: str = Index()
    status: str = Field(..., description='')
    status_icon: str | None = Field(None, description='The status icon to show in UI.')
    old_request_id: str | None = Field(None, description='Original request ID from a migrated job.')
    upload_failed_files: list[str] = Field(
        [], description='List of files that failed during batch upload.'
    )
    pipeline: str | None = Field(None, description='The name of the pipeline.')

    # metrics
    count_batch_error: int = Field(0, description='')
    count_upload_retries: int = Field(0, description='Number of retries for batch upload process.')
    count_batch_group_success: int = Field(0, description='')
    count_batch_indicator_success: int = Field(0, description='')
    count_download_group: int = Field(0, description='')
    count_download_indicator: int = Field(0, description='')
    date_convert_start: datetime | None = Field(None, description='')
    date_convert_complete: datetime | None = Field(None, description='')
    date_download_start: datetime | None = Field(None, description='')
    date_download_complete: datetime | None = Field(None, description='')
    date_upload_start: datetime | None = Field(None, description='')
    date_upload_complete: datetime | None = Field(None, description='')

    # Per-job backoff fields
    # NOTE: retry_after is pre-computed and stored rather than derived from failure_count.
    # This means backoff config changes (via API) won't affect already-scheduled retries.
    # Alternative: compute dynamically from failure_count + date_failed to pick up config
    # changes immediately. Trade-offs:
    # - Slightly more computation per job in get_next_for_task()
    # - Harder to see "when can this job retry?" in DB - would need to manually calculate
    #   backoff from failure_count using the exponential formula + jitter
    retry_after: datetime | None = Field(
        None,
        description='When this job can be retried (backoff expiry time). None = can run now.',
    )
    failure_count: int = Field(
        0,
        description='Consecutive failures at current stage (resets on success).',
    )
    total_retry_count: int = Field(
        0,
        description='Total number of retries across job lifetime (does not reset on success).',
    )

    @property
    def convert_runtime(self):
        """Calculate convert runtime."""
        if self.date_convert_start and self.date_convert_complete:
            return self.date_convert_complete - self.date_convert_start
        return None

    @property
    def download_runtime(self):
        """Calculate download runtime."""
        if self.date_download_start and self.date_download_complete:
            return self.date_download_complete - self.date_download_start
        return None

    @property
    def upload_runtime(self):
        """Calculate upload runtime."""
        if self.date_upload_start and self.date_upload_complete:
            return self.date_upload_complete - self.date_upload_start
        return None

    def is_in_backoff(self, now: datetime | None = None) -> bool:
        """Check if job is currently in backoff period.

        Args:
            now: Optional pre-computed timestamp. If None, uses current time.
                 Pass this when checking multiple jobs in a loop for efficiency.
        """
        if self.retry_after is None:
            return False
        if now is None:
            now = datetime.now(UTC)
        return now < self.retry_after

    @property
    def total_runtime(self):
        """Calculate total runtime."""
        if self.date_download_start and self.date_upload_complete:
            return self.date_upload_complete - self.date_download_start
        return None

    @field_validator('status')
    @classmethod
    def _title_case(cls, v: str) -> str:
        return ' '.join([w.title() for w in v.split(' ')])

    @model_validator(mode='before')
    @classmethod
    def _compute_status_icon(cls, values: dict) -> dict:
        status_icon_map = {
            'download in progress': 'file_download',
            'download complete': 'file_download',
            'convert in progress': 'change_circle',
            'convert complete': 'change_circle',
            'failed': 'error_outline',
            'pending': 'help_outline',
            'retry pending': 'replay',
            'upload in progress': 'file_upload',
            'upload complete': 'check',
        }
        if isinstance(values, dict) and 'status' in values:
            values['status_icon'] = (
                status_icon_map.get(values.get('status', '').lower()) or 'help_outline'
            )
        return values

    @field_serializer('*')
    @classmethod
    def _serialize_arrow(cls, v: Any, _info) -> Any:
        if isinstance(v, arrow.Arrow):
            return v.isoformat()
        return v
