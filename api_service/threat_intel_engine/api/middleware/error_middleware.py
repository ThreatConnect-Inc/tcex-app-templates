"""Middleware module"""
# first-party
from more import error


# pylint: disable=unused-argument
class ErrorMiddleware:
    """Middleware module"""

    # pylint: disable=no-self-use
    def process_resource(self, _req, _resp, resource, _params):
        """Process resource method."""
        resource.error = error
