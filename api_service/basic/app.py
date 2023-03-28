"""ThreatConnect API Service App"""

# third-party
import falcon
from tcex import TcEx
from tcex.input.input import Input

# first-party
from api_service_app import ApiServiceApp


class TcExMiddleware:
    """TcEx middleware module"""

    def __init__(self, inputs: Input, tcex: TcEx):
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

        # create Falcon API with tcex middleware
        # pylint: disable=not-callable
        self.api = falcon.APP(middleware=[TcExMiddleware(inputs=self.inputs, tcex=self.tcex)])

        # Add routes
        self.api.add_route('/one', OneResource())
        self.api.add_route('/two', TwoResource())
        self.tcex.log.trace(f'inputs: {self.inputs.model.dict()}')

    def api_event_callback(self, environ, response_handler):
        """Run the trigger logic."""
        return self.api(environ, response_handler)
