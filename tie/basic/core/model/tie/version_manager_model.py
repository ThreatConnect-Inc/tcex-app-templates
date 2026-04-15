"""Model Definition"""

from datetime import UTC, datetime

from pydantic import Field, field_serializer

from core.json_db import Index
from core.model.model_base import ModelBase


class VersionManagerModel(ModelBase):
    """Model Definition"""

    id: str = Index()
    version: str = Field(..., description='')
    installation_date: datetime = Field(default_factory=lambda: datetime.now(UTC), description='')

    @field_serializer('installation_date')
    def serialize_datetime(self, v: datetime, _info) -> str:
        """Serialize datetime to string."""
        return v.strftime('%Y-%m-%d %H:%M:%S')
