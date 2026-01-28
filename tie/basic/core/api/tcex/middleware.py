"""ThreatConnect Webhook Service App"""

# standard library
from typing import Any

# third-party
from tcex import TcEx

# first-party
# TODO: Make AppBaseModel abstract and in core, import from that here.
from app_inputs import AppBaseModel
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.middleware_abc import MiddlewareABC


# pylint: disable=unused-argument
class TcExMiddleware(MiddlewareABC):
    """Standard middleware for all API service apps.

    Injects tcex, args, and logger into resources.
    """

    def __init__(self, args: AppBaseModel, tcex: TcEx):
        """Initialize instance properties."""
        self.args = args
        self.tcex = tcex
        self.log = tcex.log

    def process_resource(
        self,
        req: FalconRequest,  # noqa: ARG002
        resp: FalconResponse,  # noqa: ARG002
        resource: Any,
        params: dict,  # noqa: ARG002
    ):
        """Process resource method."""
        resource.args = self.args
        resource.log = self.log
        resource.tcex = self.tcex
