"""Model Definition"""

from datetime import datetime

from pydantic import Field

from core.model.response.paginated_response import PaginatedResponseModel
from core.model.tie.job_request_base_model import JobRequestBaseModel


class JobRequestModel(JobRequestBaseModel):
    """Model Definition"""

    # Custom properties
    start_time: datetime = Field(..., description='The start time for the job.')
    end_time: datetime = Field(..., description='The end time for the job.')
    sample_types: list[str] = Field([], description='')


class AdHocJobRequestModel(JobRequestModel):
    """Model Definition"""

    job_type: str = 'ad-hoc'


class JobRequestPaginatedResponseModel(PaginatedResponseModel[JobRequestModel]):
    """Collection response model."""
