"""Model Definition"""

# third-party
import arrow
from pydantic import BaseModel, Extra, Field, validator


class JobRequestBaseModel(BaseModel):
    """Model Definition"""

    date_completed: arrow.Arrow | None = Field(None, description='')
    date_failed: arrow.Arrow | None = Field(None, description='')
    date_queued: arrow.Arrow = Field(..., description='')
    date_started: arrow.Arrow | None = Field(None, description='')
    job_type: str = Field(..., description='')
    request_id: str = Field(..., description='')
    status: str = Field(..., description='')
    status_icon: str | None = Field(None, description='The status icon to show in UI.')

    # pylint: disable=no-self-argument
    @validator('status')
    def _title_case(cls, v):
        return ' '.join([w.title() for w in v.split(' ')])

    @validator('status_icon', pre=True)
    def _status_icon(cls, _, values):
        status_icon_map = {
            'download in progress': 'file_download',
            'download complete': 'file_download',
            'convert in progress': 'change_circle',
            'convert complete': 'change_circle',
            'failed': 'error_outline',
            'pending': 'help_outline',
            'upload in progress': 'file_upload',
            'upload complete': 'check',
        }
        return status_icon_map.get(values.get('status').lower()) or 'help_outline'

    class Config:
        """Model Config"""

        arbitrary_types_allowed = True
        extra = Extra.allow
        json_encoders = {arrow.Arrow: lambda v: v.isoformat()}
        orm_mode = True
