"""ThreatConnect Webhook Service App"""

# standard library
from typing import TYPE_CHECKING

# first-party
from api.middleware.middleware_abc import MiddlewareABC

if TYPE_CHECKING:
    # third-party
    import falcon
    from tcex import TcEx

    # first-party
    from app_inputs import AppBaseModel


# pylint: disable=unused-argument
class TcExMiddleware(MiddlewareABC):
    """Standard middleware for all API service apps.

    Injects tcex, args, and logger into resources.
    """

    def __init__(self, args: 'AppBaseModel', tcex: 'TcEx'):
        """Initialize class properties.

        Args:
            args: Pydantic Basemodel with inputs for the class
            tcex: An instance of tcex
            v2: Instance of the V2 API wrapper
        """
        self.args = args
        self.tcex = tcex
        self.log = tcex.log

    def process_resource(self, _req, _resp, resource, _params):
        """Process resource method."""
        resource.args = self.args
        resource.log = self.log
        resource.tcex = self.tcex

    def process_request(self, req: 'falcon.Request', _resp: 'falcon.Response'):
        """Process the request before routing it."""

        self.log.debug(f'Handling request: {req}')

    def process_response(
        self,
        req: 'falcon.Request',
        resp: 'falcon.Response',
        _resource: object,
        _req_succeeded: bool,
    ):
        """Post-processing of the response (after routing)."""
        self.log.debug(f'Returning response: {req} ==> {resp}')
