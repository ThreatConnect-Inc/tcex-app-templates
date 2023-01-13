"""Declares an abstract base class for Middleware."""
# standard library
from abc import ABC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # standard library
    from typing import Dict

    # third-party
    import falcon


class MiddlewareABC(ABC):
    """Abstract base class for all middleware implementations."""

    def process_request(self, req: 'falcon.Request', resp: 'falcon.Response'):
        """Process the request before routing it.

        Note:
            Because Falcon routes each request based on req.path, a
            request can be effectively re-routed by setting that
            attribute to a new value from within process_request().

        Args:
            req: Request object that will eventually be
                routed to an on_* responder method.
            resp: Response object that will be routed to
                the on_* responder.
        """

    def process_resource(
        self, req: 'falcon.Request', resp: 'falcon.Response', resource: object, params: 'Dict'
    ):
        """Process the request after routing.

        Note:
            This method is only called when the request matches
            a route to a resource.

        Args:
            req: Request object that will be passed to the
                routed responder.
            resp: Response object that will be passed to the
                responder.
            resource: Resource object to which the request was
                routed.
            params: A 'dict'-like object representing any additional
                params derived from the route's URI template fields,
                that will be passed to the resource's responder
                method as keyword arguments.
        """

    def process_response(
        self, req: 'falcon.Request', resp: 'falcon.Response', resource: object, req_succeeded: bool
    ):
        """Post-processing of the response (after routing).

        Args:
            req: Request object.
            resp: Response object.
            resource: Resource object to which the request was
                routed. May be None if no route was found
                for the request.
            req_succeeded: True if no exceptions were raised while
                the framework processed and routed the request;
                otherwise False.
        """
