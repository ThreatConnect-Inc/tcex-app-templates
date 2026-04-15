"""Settings Module"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from arrow import arrow
from pydantic import BaseModel, ConfigDict, Field

# Default failure threshold for jobs and pipeline staleness
DEFAULT_FAILURE_THRESHOLD = timedelta(hours=48)


class MessageBrokerSettings(BaseModel):
    """Settings for the message broker."""

    schema_version: str
    active: bool = True
    provider_id: str
    topic: str
    features: list[str] = []


class FileSettings(BaseModel):
    """Settings for file handling."""

    extension_csv: str = '.csv'
    extension_gzip: str = '.gz'
    extension_bzip: str = '.bz'
    extension_json: str = '.json'
    extension_pending: str = '.temp'
    extension_processed: str = '.processed'
    extension_unknown: str = '.unknown'
    extension_zip: str = '.zip'
    separator: str = '#'  # separator used when building file names


# TODO: Would like to move status to its own thing too. Maybe a Enum?
class JobSettings(BaseModel):
    """Settings for job management."""

    status_cancelled: str = 'cancelled'
    status_failed: str = 'failed'
    status_pending: str = 'pending'
    status_retry_pending: str = 'retry pending'
    throttle_limit: int = 3


class SettingModelBase(BaseModel):
    """Base model for settings."""

    base_path: Path
    name: str
    description: str
    tc_owner: str
    date_started: datetime = Field(default_factory=lambda: datetime.now(UTC))

    notification_digest_interval: timedelta | None = None
    notification_display_name: str | None = None
    notification_types: list[str] | None = None

    mb: MessageBrokerSettings | None = None
    file: FileSettings = FileSettings()
    job: JobSettings = JobSettings()

    model_config = ConfigDict(arbitrary_types_allowed=True, extra='allow')
