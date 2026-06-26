"""."""

from uuid import UUID

from pydantic import Extra, Field

from core.message_service.model.tcva.message_types import MessageTypesBlockResponse
from core.model.model_base import ModelBase


class BlockResponseModel(ModelBase, extra=Extra.allow):
    """Enrichment Request Model"""

    data: dict | list[dict] = Field(
        ..., description='The enrichment data returned for the current request.'
    )
    indicator: str = Field(..., description='The indicator value of that was enriched.')
    indicator_type: str = Field(..., description='The type of indicator that was enriched.')
    message_type: MessageTypesBlockResponse = Field(
        ..., description='The message type from the request.'
    )
    name: str = Field(..., description='The name of the service provider.')
    provider_id: str = Field(..., description='The id of the service provider.')
    request_id: UUID = Field(..., description='The id of the request for this enrichment.')
    schema_version: str = Field('1.0.0', description='The schema version of the request.')
