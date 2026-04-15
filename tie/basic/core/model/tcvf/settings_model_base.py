"""Settings Module"""

from datetime import UTC, datetime
from pathlib import Path

from arrow import arrow
from pydantic import BaseModel, ConfigDict, Field


class SettingModelBase(BaseModel):
    """Setting Model"""

    tc_owner: str
    base_path: Path

    date_started: datetime = Field(default_factory=lambda: datetime.now(UTC))
    extension_csv: str = '.csv'
    extension_gzip: str = '.gz'
    extension_bzip: str = '.bz'
    extension_json: str = '.json'
    extension_pending: str = '.temp'
    extension_processed: str = '.processed'
    extension_unknown: str = '.unknown'
    extension_zip: str = '.zip'
    file_config_separator: str = '#'  # separator used when building file names
    status_cancelled: str = 'cancelled'
    status_failed: str = 'failed'
    status_pending: str = 'pending'
    throttle_limit: int = 3

    model_config = ConfigDict(arbitrary_types_allowed=True, extra='allow')
