"""Model Definition"""

from pydantic import Field

from core.json_db import Index
from core.model.model_base import ModelBase


class DocAnalysisThrottleModel(ModelBase):
    """Model Definition"""

    id: str = Index()
    timestamp: int | None = Field(
        default=None,
        description='Timestamp when the group was throttled, None if not throttled.',
    )
