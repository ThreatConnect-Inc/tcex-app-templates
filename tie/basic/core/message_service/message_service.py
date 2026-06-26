"""."""

import json
import logging
import threading
from collections.abc import Callable
from typing import Any

from tcex import TcEx
from tcex.app.service.mqtt_message_broker import MqttMessageBroker
from tcex.logger.trace_logger import TraceLogger
from tcex.pleb.cached_property import cached_property

from core.message_service.model.tcva.block_request_model import BlockRequestModel
from core.message_service.model.tcva.discovery_request_model import (
    DiscoveryRequestModel,
)
from core.message_service.model.tcva.enrichment_request_model import (
    EnrichmentRequestModel,
)
from core.message_service.model.tcva.investigate_request_model import (
    InvestigateRequestModel,
)
from core.message_service.model.tcva.message_types import (
    message_types_block,
    message_types_enrichment,
    message_types_investigate,
)
from core.model.model_base import ModelBase

_logger: TraceLogger = logging.getLogger('tcex')  # type: ignore


class MessageService:
    """."""

    def __init__(self, tcex: TcEx, topic, provider_id):
        """Initialize class properties."""
        self.tcex: TcEx = tcex
        self.provider_id = provider_id
        self.topic = topic
        self.log = _logger

        self.handlers = {}

    def add_message_handler(self, message_type: list[str] | str, handler: Any):
        """Add a handler."""
        if isinstance(message_type, str):
            message_type = [message_type]

        for mt in message_type:
            self.handlers[mt] = handler

    def listen(self):
        """List for message coming from broker."""
        self.message_broker.add_on_connect_callback(self.on_connect_handler)
        self.message_broker.add_on_message_callback(self.on_message_handler, topics=[self.topic])
        self.message_broker.register_callbacks()

        # start listener thread
        self.service_thread(name='broker-listener', target=self.message_broker.connect)

    @cached_property
    def message_broker(self) -> MqttMessageBroker:
        """Message Broker"""
        return MqttMessageBroker(
            broker_host=self.tcex.inputs.model.tc_svc_broker_host,
            broker_port=self.tcex.inputs.model.tc_svc_broker_port,
            broker_timeout=self.tcex.inputs.model.tc_svc_broker_conn_timeout,
            broker_token=self.tcex.inputs.model.tc_svc_broker_token,
            broker_cacert=self.tcex.inputs.model.tc_svc_broker_cacert_file,
        )

    def on_connect_handler(self, _client, _userdata, _flags, _rc):
        """On connect method for mqtt broker."""
        self.log.info(f'feature=service, event=topic-subscription, topic={self.topic}')
        self.message_broker.client.subscribe(self.topic)
        self.message_broker.client.disable_logger()

    def _load_message(self, message: dict, model: type[ModelBase]) -> ModelBase | None:
        """Load message and parse it into the given model."""
        try:
            # messages on server topic must be json objects
            data = model(**message)
        except ValueError:
            self.log.exception(f'feature=service, event=parsing-issue, message="""{message}"""')
            return None
        except Exception:
            self.log.exception(f'feature=service, event=unknown-error, message="""{message}"""')
            return None
        return data

    def _load_message_enrichment_request(
        self,
        message: str,
        model: type[BlockRequestModel | EnrichmentRequestModel | InvestigateRequestModel],
    ) -> EnrichmentRequestModel | None:
        """."""
        return self._load_message(message, model)  # type: ignore

    def _load_message_discovery_request(
        self, message: str, model: type[DiscoveryRequestModel]
    ) -> DiscoveryRequestModel | None:
        """."""
        return self._load_message(message, model)  # type: ignore

    def on_message_handler(self, _client, _userdata, message):  # noqa: PLR0912,PLR0911,C901
        """On message for mqtt."""
        # payload = msgpack.loads(message, raw=False)

        self.log.trace(f'message received {message} {message.payload}')
        if not message.payload:
            return

        try:
            payload = json.loads(message.payload)
            message_type = payload.get('message_type')
        except Exception:
            self.log.exception('feature=service, event=unknown-error')
            return

        if message_type in message_types_block:
            data = self._load_message_enrichment_request(payload, BlockRequestModel)
            if data is None:
                return
        elif message_type in message_types_enrichment:
            data = self._load_message_enrichment_request(payload, EnrichmentRequestModel)
            if data is None:
                return
        elif message_type in message_types_investigate:
            data = self._load_message_enrichment_request(payload, InvestigateRequestModel)
            if data is None:
                return
        elif message_type == 'service-discovery':
            data = self._load_message_discovery_request(payload, DiscoveryRequestModel)
            if data is None:
                return
        elif message_type is None:
            self.log.error('feature=service, event=missing-message-type')
            return
        else:
            self.log.error(
                f'feature=service, event=unknown-message-type, message_type={message_type}'
            )
            return

        # find the appropriate handler for the message type
        handler = self.handlers.get(data.message_type)
        if handler is None:
            self.log.error(
                f'feature=service, event=handler-not-found, message_type={data.message_type}'
            )
            return

        # call the handler with the message data
        self.service_thread(
            # use session_id as thread name to provide easy debugging per thread
            name=data.message_type,
            target=handler.on_message,
            args=(data,),
        )

    def publish(self, message: str):
        """Publish a message to the broker."""
        # payload = msgpack.dumps(message, use_bin_type=True)
        self.message_broker.publish(message=message, topic=self.topic)

    def service_thread(
        self,
        name: str,
        target: Callable[..., bool | None],
        args: tuple | None = None,
        kwargs: dict | None = None,
    ):
        """Start a message thread.

        Args:
            name: The name of the thread.
            target: The method to call for the thread.
            args: The args to pass to the target method.
            kwargs: Additional args.
            session_id: The current session id.
            trigger_id: The current trigger id.
        """
        self.log.info(f'feature=service, event=service-thread-creation, name={name}')
        args = args or ()
        try:
            t = threading.Thread(name=name, target=target, args=args, kwargs=kwargs, daemon=True)
            t.start()
        except Exception:
            self.log.trace('feature=service, event=service-thread-creation-error')
