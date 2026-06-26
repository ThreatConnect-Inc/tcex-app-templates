"""."""

from typing import Literal
from uuid import UUID

from pydantic import Extra, Field

from core.model.model_base import ModelBase


class DiscoveryResponseModel(ModelBase, extra=Extra.allow):
    """Service Discovery Response Model"""

    description: str = Field(..., description='The description of the service provider.')
    features: list[str] = Field(
        ..., description='The features that this service provider provides.'
    )
    message_type: Literal['service-discovery-response'] = Field(
        ..., description='The message type from the request.'
    )
    name: str = Field(..., description='The name of this service provider.')
    provider_id: str = Field(..., description='The id of this service provider.')
    request_id: UUID = Field(..., description='The id from the request.')
    schema_version: str = Field('1.0.0', description='The schema version of the request.')
    status: str = Field(..., description='The status of this service provider.')
