"""ThreatConnect Webhook Service App"""
# standard library
from typing import TYPE_CHECKING

# first-party
from api.middleware.middleware_abc import MiddlewareABC

if TYPE_CHECKING:
    # standard library
    from typing import Dict

    # third-party
    import falcon


# pylint: disable=unused-argument
class InjectablesMiddleware(MiddlewareABC):
    """Middleware that injects attributes into resources."""

    def __init__(self, **kwargs):
        """Initialize.

        Args:
            kwargs: k,v pair where each will be injected into each resource such that
                resource.k = v
        """
        self.injectables = kwargs

    def process_resource(
        self, req: 'falcon.Request', resp: 'falcon.Response', resource: object, params: 'Dict'
    ):
        """."""
        for k, v in self.injectables.items():
            setattr(resource, k, v)
