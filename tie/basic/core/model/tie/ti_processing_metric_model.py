"""Model Definition"""

from datetime import UTC, datetime

from pydantic import ConfigDict, Field, field_serializer

from core.json_db import Index
from core.model.response.paginated_response import PaginatedResponseModel
from core.model.tie.item_model import ItemModel


class TiProcessingMetricModel(ItemModel):
    """Job Request coming from API."""

    model_config = ConfigDict(extra='forbid', from_attributes=True)

    date_last_updated: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description='The date the metric was last updated.',
    )
    ti_type: str = Index(description='The TI type for the metric.')
    ti_count: int = Field(..., description='The TI count for the metric.')

    @field_serializer('date_last_updated')
    def serialize_datetime(self, v: datetime, _info) -> str:
        """Serialize datetime to ISO format."""
        return v.replace(tzinfo=UTC).isoformat()


class TiProcessingMetricPaginatedResponseModel(PaginatedResponseModel[TiProcessingMetricModel]):
    """Collection of TiProcessingMetricModel."""
