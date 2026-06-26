"""."""

from uuid import UUID

from pydantic import Extra, Field

from core.message_service.model.tcva.message_types import MessageTypesInvestigate
from core.model.model_base import ModelBase


class InvestigateRequestModel(ModelBase, extra=Extra.allow):
    """Enrichment Request Model"""

    indicator: str = Field(..., description='The indicator value that should be enriched.')
    indicator_type: str = Field(..., description='The type of the indicator provided.')
    message_type: MessageTypesInvestigate = Field(
        ...,
        description='The message type of the request. This is used to route the request.',
    )
    provider_ids: list[str] = Field(
        ...,
        description=(
            'This parameter is used to filter providers. If no '
            'providers are provided, all providers should return data.'
        ),
    )
    request_id: UUID = Field(..., description='The id of the enrichment request.')
    response_topic: str = Field(
        ...,
        description='The message broker topic where the response data should be published.',
    )
    schema_version: str = Field('1.0.0', description='The schema version of the request.')
