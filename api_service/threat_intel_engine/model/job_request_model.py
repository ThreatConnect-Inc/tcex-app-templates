"""Model Definition"""
# standard library
from typing import List, Optional

# third-party
import arrow
from pydantic import Field, validator

from .job_request_base_model import JobRequestBaseModel


# pylint: disable=no-self-argument,no-self-use
class JobRequestModel(JobRequestBaseModel):
    """Model Definition"""

    # metrics
    count_batch_error: int = Field(0, description='')
    count_batch_group_success: int = Field(0, description='')
    count_batch_indicator_success: int = Field(0, description='')
    count_download_group: int = Field(0, description='')
    count_download_indicator: int = Field(0, description='')

    # metrics
    date_convert_start: Optional[arrow.Arrow] = Field(None, description='')
    date_convert_complete: Optional[arrow.Arrow] = Field(None, description='')
    date_download_start: Optional[arrow.Arrow] = Field(None, description='')
    date_download_complete: Optional[arrow.Arrow] = Field(None, description='')
    date_upload_start: Optional[arrow.Arrow] = Field(None, description='')
    date_upload_complete: Optional[arrow.Arrow] = Field(None, description='')

    # task settings
    last_modified_filter_start: Optional[arrow.Arrow] = Field(None, description='')
    last_modified_filter_end: Optional[arrow.Arrow] = Field(None, description='')
    group_types: List[str] = Field([], description='')
    indicator_types: List[str] = Field([], description='')

    # hybrid properties
    convert_runtime: Optional[str] = Field(None, description='')
    download_runtime: Optional[str] = Field(None, description='')
    upload_runtime: Optional[str] = Field(None, description='')
    total_runtime: Optional[str] = Field(None, description='')

    @validator('convert_runtime', 'download_runtime', 'upload_runtime', 'total_runtime', pre=True)
    def _convert_timedelta(cls, v):
        if v:
            return str(v)
        return v

    @validator('group_types', 'indicator_types', pre=True)
    def _split_ti_types(cls, v):
        return v.split(',') if v else []
