"""."""

from pydantic import Field

from core.model.model_base import ModelBase


class EnrichmentTimelineModel(ModelBase):
    """Enrichment Timeline Model"""

    elapsed_time: str = Field(..., description='The elapsed time the phase.')
    phase: str = Field(..., description='The phase of the enrichment.')
    runtime: str = Field(..., description='The runtime of the phase.')
