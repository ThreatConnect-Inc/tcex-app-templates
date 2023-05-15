"""App Module"""
# standard library
from abc import abstractmethod
from typing import cast
from wsgiref.types import WSGIApplication

# third-party
from pydantic import ValidationError
from tcex import TcEx

# first-party
from app_inputs import AppBaseModel, AppInputs


class ApiServiceApp:
    """Service App Class"""

    def __init__(self, _tcex: TcEx):
        """Initialize class properties."""
        self.tcex = _tcex

        # automatically process inputs on init
        self._update_inputs()

        # properties
        self.exit_message = 'Success'
        self.in_ = cast(AppBaseModel, self.tcex.inputs.model)
        self.in_unresolved = cast(AppBaseModel, self.tcex.inputs.model_unresolved)
        self.log = self.tcex.log

        self.wsgi_app: WSGIApplication | None = None

    def _update_inputs(self):
        """Add an custom App models and run validation."""
        try:
            AppInputs(inputs=self.tcex.inputs).update_inputs()
        except ValidationError as ex:
            self.tcex.exit.exit(code=1, msg=self.tcex.inputs.validation_exit_message(ex))

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
        if self.wsgi_app is None:
            self.wsgi_app = self.get_wsgi_app()

        return self.wsgi_app(environ, response_handler)

    @abstractmethod
    def get_wsgi_app(self) -> WSGIApplication:
        """Create and return a WSGI application to handle requests."""
