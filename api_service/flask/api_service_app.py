"""App Module"""
# standard library
from abc import ABC, abstractmethod
from urllib.parse import urlparse

# third-party
from pydantic import ValidationError
from tcex import TcEx
from tcex.input.input import Input
from tcex.logger.trace_logger import TraceLogger
from wsgi_types import WSGIApplication

# first-party
from app_inputs import AppInputs


class ApiServiceApp(ABC):
    """Service App Class"""

    def __init__(self, _tcex: 'TcEx'):
        """Initialize class properties."""
        self.tcex: 'TcEx' = _tcex

        # properties
        self.exit_message = 'Success'
        self.inputs: 'Input' = self.tcex.inputs
        self.log: 'TraceLogger' = self.tcex.log

        # automatically parse args on init
        self._update_inputs()

        self.app = None

    def _update_inputs(self) -> None:
        """Add an custom App models and run validation."""
        try:
            AppInputs(inputs=self.tcex.inputs)
        except ValidationError as ex:
            self.tcex.exit(code=1, msg=ex)

    def setup(self) -> None:
        """Perform setup actions."""
        self.log.trace('feature=app, event=setup')

    def shutdown_callback(self) -> None:
        """Handle the shutdown message."""
        self.log.trace('feature=app, event=shutdown-callback')

    def teardown(self) -> None:
        """Perform teardown actions."""
        self.log.trace('feature=app, event=teardown')

    def api_event_callback(self, environ, response_handler):
        """Handle a WSGI call.

        The first time this function is called, it will call get_wsgi_app() to create the wsgi app,
        passing the url_prefix for this app.
        """

        request_url = environ.get('request_url')
        path_info = environ.get('PATH_INFO')

        request_url = urlparse(request_url).path

        if path_info:
            base_path = request_url[: -len(path_info)]
        else:
            base_path = request_url

        if base_path.endswith('/'):
            base_path = base_path[:-1]

        if self.app is None:
            self.app = self.get_wsgi_app(base_path)

        # we need path_info to be the full path from the url, not just the part for our app.
        environ['PATH_INFO'] = request_url

        return self.app(environ, response_handler)

    @abstractmethod
    def get_wsgi_app(self, url_prefix: str) -> 'WSGIApplication':
        """Create and return a WSGI application to handle requests."""
