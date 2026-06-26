"""."""

import logging

from tcex.logger.trace_logger import TraceLogger

from core.message_service.message_handler.message_handler_abc import MessageHandlerABC
from core.message_service.message_service import MessageService
from core.message_service.model.tcva.enrichment_request_model import (
    EnrichmentRequestModel,
)
from core.message_service.model.tcva.enrichment_response_model import (
    EnrichmentResponseModel,
)

_logger: TraceLogger = logging.getLogger('tcex')  # type: ignore


class EnrichmentHandler(MessageHandlerABC):
    """."""

    def __init__(self, message_service: MessageService, settings, sdk):
        """Initialize instance properties."""
        super().__init__(message_service, settings)
        self.sdk = sdk

    def enrich(self, message: EnrichmentRequestModel) -> EnrichmentResponseModel:
        """."""
        resp_data = {}
        try:
            params = {'value': message.indicator}
            resp = self.sdk.get('/indicators', params=params)
            resp_data = resp.json()['indicators'][0]
        except Exception:
            self.log.exception('Error processing response')

        return EnrichmentResponseModel(
            data=resp_data,
            indicator=message.indicator,
            indicator_type=message.indicator_type,
            message_type=f'{message.message_type}-response',  # type: ignore
            name=self.settings.name,
            provider_id=self.settings.mb.provider_id,
            request_id=message.request_id,
            schema_version=self.settings.mb.schema_version,
        )

    def on_post(self, message: EnrichmentRequestModel):
        """."""
        return self.enrich(message).dict(exclude_none=True)

    def on_message(self, message: EnrichmentRequestModel):
        """."""
        self.on_message_wrapper(message, self.enrich, ack=True)
