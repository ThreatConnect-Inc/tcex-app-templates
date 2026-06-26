"""."""

import logging

from pydantic import BaseModel
from tcex.logger.trace_logger import TraceLogger

from core.message_service.message_handler.message_handler_abc import MessageHandlerABC
from core.message_service.model.tcva.discovery_request_model import (
    DiscoveryRequestModel,
)
from core.message_service.model.tcva.discovery_response_model import (
    DiscoveryResponseModel,
)

_logger: TraceLogger = logging.getLogger('tcex')  # type: ignore


class DiscoveryHandler(MessageHandlerABC):
    """."""

    def on_get(self, message: DiscoveryRequestModel):
        """Discovery request handler."""
        service_discovery = self.discovery(message)
        response = self.discovery_response(message, service_discovery)
        return response.dict(exclude_none=True)

    @property
    def discovery_data(self):
        """."""
        return {
            'description': self.settings.description,
            'message_type': 'service-discovery-response',
            'name': self.settings.name,
            'provider_id': self.settings.mb.provider_id,
            'features': self.settings.mb.features,
            'status': self.settings.mb.active,
            'schema_version': self.settings.mb.schema_version,
        }

    def discovery(self, message: DiscoveryRequestModel):
        """."""
        service_discovery_response = DiscoveryResponseModel(
            request_id=message.request_id, **self.discovery_data
        )
        return self.discovery_response(message, service_discovery_response)

    def discovery_response(
        self, request: DiscoveryRequestModel, response: DiscoveryResponseModel
    ) -> DiscoveryResponseModel | None:
        """."""
        # if features are specified and this provider does not have the feature, return None
        if request.requested_features and not set(response.features).intersection(
            set(request.requested_features)
        ):
            return None
        try:
            response_msg = response
        except Exception:
            self.log.exception('Error publishing message')
            return None
        self.log.trace(f'discover-message-response="""{response_msg}"""')
        return response_msg

    def on_message(self, message: BaseModel):
        """."""
        service_discovery = self.discovery(message)

        response = self.discovery_response(message, service_discovery)
        self.message_service.message_broker.publish(
            response.json(exclude_none=True), topic=message.response_topic
        )
