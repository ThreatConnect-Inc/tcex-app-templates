"""Model Definition"""

# standard library

# standard library
from datetime import datetime

# third-party
from pydantic import Field

# first-party
from app_inputs import AdvancedSettingsModel
from core.json_db import Embedded
from core.model.response.paginated_response import PaginatedResponseModel
from core.model.tie.job_request_base_model import JobRequestBaseModel


class JobRequestModel(JobRequestBaseModel):
    """Model Definition"""

    advanced_settings: AdvancedSettingsModel = Embedded(AdvancedSettingsModel(), description='')

    # Custom properties
    start_time: datetime = Field(..., description='The start time for the job.')
    end_time: datetime = Field(..., description='The end time for the job.')
    sample_types: list[str] = Field([], description='')


class AdHocJobRequestModel(JobRequestModel):
    """Model Definition"""

    job_type: str = 'ad-hoc'


class JobRequestPaginatedResponseModel(PaginatedResponseModel[JobRequestModel]):
    """Collection response model."""
