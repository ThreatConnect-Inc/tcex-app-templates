"""Model Definition"""

from datetime import UTC, datetime
from typing import ClassVar

from pydantic import Field

from core.json_db import Index
from core.model.model_base import ModelBase
from core.model.response.paginated_response import PaginatedResponseModel


class NotificationModel(ModelBase):
    """Stored notification record."""

    id: str = Index()
    date_added: datetime = Field(default_factory=lambda: datetime.now(UTC))
    category: str = Field(
        ...,
        description='app_startup, app_shutdown, job_retrying, job_failed, job_recovered, manual',
    )
    notification_type: str = Field(..., description='TC notification type label')
    priority: str = Field(..., description='Low, Medium, High')
    message: str = Field(...)
    job_ids: list[str] = Field(
        default_factory=list, description='Job request IDs related to this notification'
    )
    send_status: str | None = Field(None, description='success, failed, or None if not sent')
    send_status_code: int | None = Field(None, description='HTTP status code from API')
    send_status_text: str | None = Field(None, description='Error text on failure')
    api_request: dict | None = Field(None, description='Request sent to TC Notification API')
    api_response: dict | None = Field(None, description='Response from TC Notification API')

    class Config:
        """Model Config"""

        json_encoders: ClassVar[dict] = {
            datetime: lambda v: v.strftime('%Y-%m-%d %H:%M:%S'),
        }


class NotificationPaginatedResponseModel(PaginatedResponseModel[NotificationModel]):
    """Paginated response for notifications."""
