"""Model Definition"""

# third-party
import arrow
from pydantic import Field, validator

from .job_request_base_model import JobRequestBaseModel


# pylint: disable=no-self-argument
class JobRequestModel(JobRequestBaseModel):
    """Model Definition"""

    # metrics
    count_batch_error: int = Field(0, description='')
    count_batch_group_success: int = Field(0, description='')
    count_batch_indicator_success: int = Field(0, description='')
    count_download_group: int = Field(0, description='')
    count_download_indicator: int = Field(0, description='')

    # metrics
    date_convert_start: arrow.Arrow | None = Field(None, description='')
    date_convert_complete: arrow.Arrow | None = Field(None, description='')
    date_download_start: arrow.Arrow | None = Field(None, description='')
    date_download_complete: arrow.Arrow | None = Field(None, description='')
    date_upload_start: arrow.Arrow | None = Field(None, description='')
    date_upload_complete: arrow.Arrow | None = Field(None, description='')

    # task settings
    last_modified_filter_start: arrow.Arrow | None = Field(None, description='')
    last_modified_filter_end: arrow.Arrow | None = Field(None, description='')
    group_types: list[str] = Field([], description='')
    indicator_types: list[str] = Field([], description='')

    # hybrid properties
    convert_runtime: str | None = Field(None, description='')
    download_runtime: str | None = Field(None, description='')
    upload_runtime: str | None = Field(None, description='')
    total_runtime: str | None = Field(None, description='')

    @validator('convert_runtime', 'download_runtime', 'upload_runtime', 'total_runtime', pre=True)
    def _convert_timedelta(cls, v):
        if v:
            return str(v)
        return v

    @validator('group_types', 'indicator_types', pre=True)
    def _split_ti_types(cls, v):
        return v.split(',') if v else []
