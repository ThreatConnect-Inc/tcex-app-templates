"""Model Definition"""

from datetime import UTC, datetime
from typing import ClassVar

from pydantic import Extra, Field

from core.json_db import Index
from core.model.response.paginated_response import PaginatedResponseModel
from core.model.tie.item_model import ItemModel


class TiProcessingMetricModel(ItemModel):
    """Job Request coming from API."""

    date_last_updated: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description='The date the metric was last updated.',
    )
    ti_type: str = Index(description='The TI type for the metric.')
    ti_count: int = Field(..., description='The TI count for the metric.')

    class Config:
        """Model Config"""

        extra = Extra.forbid
        json_encoders: ClassVar[dict] = {datetime: lambda v: v.replace(tzinfo=UTC).isoformat()}
        orm_mode = True


class TiProcessingMetricPaginatedResponseModel(PaginatedResponseModel[TiProcessingMetricModel]):
    """Collection of TiProcessingMetricModel."""
