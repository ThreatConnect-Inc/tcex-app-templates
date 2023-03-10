"""Model Definition"""
# third-party
import arrow
from pydantic import BaseModel, Extra, Field


class TiProcessingMetricModel(BaseModel):
    """Job Request coming from API."""

    id: str = Field(..., description='')
    date_last_updated: arrow.Arrow = Field(
        None, description='The date the metric was last updated.'
    )
    ti_type: str = Field(..., description='The TI type for the metric.')
    ti_count: int = Field(..., description='The TI count for the metric.')

    class Config:
        """Model Config"""

        arbitrary_types_allowed = True
        extra = Extra.forbid
        json_encoders = {arrow.Arrow: lambda v: v.isoformat()}
        orm_mode = True
