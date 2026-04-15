"""."""

import logging
from abc import abstractmethod

from pydantic import BaseModel
from tcex.logger.trace_logger import TraceLogger

from core.message_service.message_service import MessageService
from core.message_service.model.tcva.enrichment_acknowledge_model import (
    EnrichmentAcknowledgeResponseModel,
)
from core.message_service.model.tcva.enrichment_request_model import (
    EnrichmentRequestModel,
)

_logger: TraceLogger = logging.getLogger('tcex')  # type: ignore


class MessageHandlerABC:
    """."""

    def __init__(self, message_service: MessageService, settings):
        """Initialize instance properties."""
        self.message_service = message_service
        self.log = _logger
        self.settings = settings

    def not_supported_provider(self, provider_ids):
        """."""
        if provider_ids and self.settings.mb.provider_id not in provider_ids:
            return True
        return False

    def on_message_wrapper(self, message, fn, ack=True):
        """Wrap the on_message method."""
        if self.not_supported_provider(message.provider_ids):
            return
        if ack:
            self.publish_acknowledgment(message)
        response = fn(message)
        self.publish_response(response, message.response_topic)

    @abstractmethod
    def on_message(self, message: BaseModel):
        """."""

    def publish_acknowledgment(self, message):
        """Publish an acknowledgment message for the enrichment request."""
        ack_response = self.acknowledge_data(message)
        self.publish_to_broker(ack_response, message.response_topic)

    def publish_response(self, response, topic):
        """Publish the enrichment response message."""
        try:
            self.publish_to_broker(response, topic)
        except Exception:
            self.log.exception('Error publishing message')

    def publish_to_broker(self, message, topic):
        """Publish messages to the message broker."""
        self.message_service.message_broker.publish(
            message.model_dump_json(exclude_none=True), topic=topic
        )

    def acknowledge_data(
        self, message: EnrichmentRequestModel
    ) -> EnrichmentAcknowledgeResponseModel:
        """."""
        return EnrichmentAcknowledgeResponseModel(
            indicator=message.indicator,
            indicator_type=message.indicator_type,
            message_type=f'{message.message_type}-ack',  # type: ignore
            name=self.settings.name,
            provider_id=self.settings.mb.provider_id,
            request_id=message.request_id,
            schema_version=self.settings.mb.schema_version,
        )
