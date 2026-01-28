"""Endpoint Base Class"""

# first-party
from core.api.endpoint.endpoint_base_abc import EndpointBaseABC
from core.task.tasks import Tasks
from sdk.sdk import SDK


class EndpointBase(EndpointBaseABC):
    """Endpoint Base Class"""

    tasks: Tasks
    sdk: SDK
