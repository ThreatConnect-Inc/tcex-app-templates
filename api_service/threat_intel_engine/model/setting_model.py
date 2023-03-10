"""Model Definition"""
# standard library
from pathlib import Path

# third-party
import arrow
from pydantic import BaseModel, Field


class SettingsModel(BaseModel):
    """Model Definition"""

    #
    # App Inputs
    #
    external_owner: str = Field(..., description='Owner to retrieve data from in external TC.')
    tql: str = Field(..., description='TQL query to run against external TC.')

    # Common Settings (same across most apps of this type)
    owner: str = Field(..., description='TC Owner to ingest data into.')
    base_path: Path = Field(..., description='Base path for storing files. Should be tc out path.')
    initial_backfill_days: int = Field(
        30, description='How many days of backfill when first started.'
    )
    time_chunk_size_hours: int = Field(
        1, description='Size of time chunks for normal scheduled requests.'
    )
    time_chunk_size_hours_backfill: int = Field(
        24, description='Size of time chunks for backfill requests.'
    )

    #
    # Framework Inputs
    #

    date_started: arrow.Arrow = Field(..., description='Date the app started.')
    extension_csv: str = Field('.csv', description='')
    extension_gzip: str = Field('.gz', description='')
    extension_bzip: str = Field('.bz', description='')
    extension_json: str = Field('.json', description='')
    extension_pending: str = Field('.temp', description='')
    extension_processed: str = Field('.processed', description='')
    extension_unknown: str = Field('.unknown', description='')
    extension_zip: str = Field('.zip', description='')
    file_config_separator: str = Field(
        '#',
        description='The separator used in configuration file names',
    )
    status_cancelled: str = Field('cancelled', description='')
    status_failed: str = Field('failed', description='')
    status_pending: str = Field('pending', description='')
    throttle_limit: int = Field(3, description='Used to throttle download.')
    working_dir_download: str = Field(..., description='')
    working_dir_batch: str = Field(..., description='')
    working_dir_convert: str = Field(..., description='')
    working_dir_copy_group_files: str = Field(..., description='')
    working_dir_upload: str = Field(..., description='')

    class Config:
        """Pydantic Config"""

        arbitrary_types_allowed = True
        json_encoders = {arrow.Arrow: lambda v: v.isoformat()}
