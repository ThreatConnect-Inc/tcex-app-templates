"""ThreatConnect Webhook Service App"""
# standard library
import logging
from typing import TYPE_CHECKING

# third-party
from api.middleware.middleware_abc import MiddlewareABC
from more import session

if TYPE_CHECKING:
    # third-party
    import falcon

logger = logging.getLogger('tcex')


# pylint: disable=unused-argument
class DbMiddleware(MiddlewareABC):
    """Standard middleware for all API service apps.

    Injects tcex, args, and logger into resources.
    """

    def process_resource(self, _req, _resp, resource, _params):
        """Process resource method."""
        resource.session = session()

    def process_response(
        self,
        _req: 'falcon.Request',
        _resp: 'falcon.Response',
        resource: object,
        _req_succeeded: bool,
    ):
        """Post-processing of the response (after routing)."""
        try:
            if resource and resource.session.is_active:
                resource.session.close()
        except Exception:
            logger.exception('Failed to close session.')
