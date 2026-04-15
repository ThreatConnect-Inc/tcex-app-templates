"""."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from core.model.model_base import ModelBase


class DiscoveryRequestModel(ModelBase, extra='allow'):
    """Service Discovery Request Model"""

    message_type: Literal['service-discovery'] = Field(
        ...,
        description='The message type of the request. This is used to route the request.',
    )
    requested_features: list[str] = Field(
        [],
        description=(
            'This parameter is used to filter features. If no requested'
            'features are provided, all features should be returned.'
        ),
    )
    request_id: UUID = Field(..., description='The id of the discovery request.')
    response_topic: str = Field(
        ...,
        description='The message broker topic where the response data should be published.',
    )
    schema_version: str = Field('1.0.0', description='The schema version of the request.')
