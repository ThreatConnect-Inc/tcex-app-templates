"""."""

from uuid import UUID

from pydantic import Field

from core.message_service.model.tcva.message_types import MessageTypesInvestigateAck
from core.model.model_base import ModelBase


class InvestigateAcknowledgeResponseModel(ModelBase):
    """Enrichment Request Model"""

    indicator: str = Field(..., description='The indicator value of that was enriched.')
    indicator_type: str = Field(..., description='The type of indicator that was enriched.')
    message_type: MessageTypesInvestigateAck = Field(
        ..., description='The message type from the request.'
    )
    name: str = Field(..., description='The name of the service provider.')
    provider_id: str = Field(..., description='The id of the service provider.')
    request_id: UUID = Field(..., description='The id of the request for this enrichment.')
    schema_version: str = Field('1.0.0', description='The schema version of the request.')
