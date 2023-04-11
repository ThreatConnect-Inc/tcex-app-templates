"""ThreatConnect API Service App"""
# standard library
import itertools
import threading
from collections.abc import Iterable
from functools import cached_property
from typing import TYPE_CHECKING
from wsgiref.types import StartResponse, WSGIEnvironment

# third-party
import falcon

# first-party
from api_service_app import ApiServiceApp

if TYPE_CHECKING:
    # third-party
    from tcex import TcEx
    from tcex.input.input import Input


class TcExMiddleware:
    """TcEx middleware module"""

    def __init__(self, inputs: 'Input', tcex: 'TcEx'):
        """Initialize class properties"""
        self.inputs = inputs
        self.tcex = tcex

    def process_resource(  # pylint: disable=unused-argument
        self, req: 'falcon.Request', resp: 'falcon.Response', resource: object, params: dict
    ):
        """Process resource method."""
        resource.inputs = self.inputs
        resource.log = self.tcex.log
        resource.tcex = self.tcex


class OneResource:
    """Handle request to /one endpoint."""

    # provided by TcEx middleware
    args = None
    log = None
    tcex = None

    def on_get(self, req, resp):  # pylint: disable=unused-argument
        """Handle GET requests"""
        data = {'data': 'one'}
        resp.media = data


class TwoResource:
    """Handle request to /two endpoint."""

    # provided by TcEx middleware
    args = None
    log = None
    tcex = None

    def on_get(self, req, resp):  # pylint: disable=unused-argument
        """Handle GET requests"""
        data = {'data': 'two'}
        resp.media = data


class App(ApiServiceApp):
    """API Service App"""

    def __init__(self, _tcex):
        """Initialize class properties."""
        super().__init__(_tcex)

        self.tcex.log.trace(f'inputs: {self.inputs.model.dict()}')

    def build_falcon_app(self):
        """Build falcon app."""

        # create Falcon API with tcex middleware
        # pylint: disable=not-callable
        api = falcon.App(middleware=[TcExMiddleware(inputs=self.inputs, tcex=self.tcex)])

        # Add routes
        api.add_route('/one', OneResource())
        api.add_route('/two', TwoResource())

        return api

    @cached_property
    def app_pool(self):
        """Return an iterator of falcon apps.

        Each app instance should only handle one request at a time.  This simplifies concurrency
        issues.  This method returns a cyclic iterator of 6 app objects that are used to handle
        requests in a round-robin style.

        Note: this DOES NOT guarantee that requests are handled in a thread-safe way; for example,
        if requests access a non-thread-safe resource, such as a database connection.
        """
        return itertools.cycle([(threading.Lock(), self.build_falcon_app()) for _ in range(6)])

    def api_event_callback(
        self, environ: WSGIEnvironment, start_response: StartResponse
    ) -> Iterable[bytes]:
        """Handle requests to the API Service."""
        lock, app = next(self.app_pool)

        # iterate through the app pool until we get an available app
        while not lock.acquire(blocking=False):
            lock, app = next(self.app_pool)
        try:
            self.log.trace(f'feature=api-service, event=event-callback, app={id(app)}')
            if not environ['PATH_INFO'].startswith('/'):
                environ['PATH_INFO'] = '/' + environ['PATH_INFO']

            return app(environ, start_response)
        finally:
            lock.release()
