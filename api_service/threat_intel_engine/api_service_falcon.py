"""ThreatConnect API Service Falcon API"""
# standard library
import json
import logging
import os
from datetime import datetime
from functools import partial

# third-party
import arrow
import falcon

# first-party
from api import custom_error_handler
from api.middleware import DbMiddleware, ErrorMiddleware, TcExMiddleware, ValidationMiddleware
from api_service_app import ApiServiceApp
from more.database import request_fork_lock

logger = logging.getLogger('tcex')


class DatetimeEncoder(json.JSONEncoder):
    """Json Encoder that supports datetime objects."""

    def default(self, o):
        """Set default encoding for datetime objects."""
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, arrow.Arrow):
            return o.isoformat()
        return super().default(o)


class ApiServiceFalcon(ApiServiceApp):
    """ThreatConnect API Service Falcon API"""

    def __init__(self, *args, **kwargs):
        """Initialize class properties."""
        super().__init__(*args, **kwargs)

        # properties
        self._ui_files = os.path.join(os.getcwd(), 'ui_build')
        self.app = falcon.App(middleware=self._middleware, sink_before_static_route=True)
        self.log = logger

        # configure app
        self._configure_app()

    def _add_media_handlers(self):
        """Add API handlers."""
        json_handler = falcon.media.JSONHandler(
            dumps=partial(json.dumps, cls=DatetimeEncoder),
        )
        extra_handlers = {
            'application/json': json_handler,
        }
        self.app.req_options.media_handlers.update(extra_handlers)  # pylint: disable=no-member
        self.app.resp_options.media_handlers.update(extra_handlers)  # pylint: disable=no-member

    def _add_redirect_and_sink(self):
        """Add redirect and sink to angular App."""
        # serve index.html specifically since `/` will not match a file (fallback returned)
        # index.html then calls ng route which will redirect to ui/dashboard
        self.app.add_static_route('/', self._ui_files, fallback_filename='index.html')

        # add routing sinks for "/ui/*", if this path is hit it indicates that
        # ng was already loaded and someone is trying to reload the page. this is
        # not technically supported, but we will redirect to the dashboard.
        self._add_routing_sinks()

    def _add_routing_sinks(self):
        """Add routing sinks to redirect all request to the UI."""

        def _ng_redirect(req: 'falcon.Request', _resp: 'falcon.Response'):
            """Redirect to angular index.html file."""
            path_count = req.path.count('/') - 1
            redirect = '/'.join(['..'] * path_count)
            raise falcon.HTTPPermanentRedirect(redirect)

        self.app.add_sink(_ng_redirect, prefix='/ui')

    def _configure_app(self):
        """Configure the Falcon App."""
        self.app.req_options.auto_parse_qs_csv = True  # auto parse csv parameters
        self.app.req_options.strip_url_path_trailing_slash = True
        self._add_redirect_and_sink()

        # add custom error handler for api
        self.app.add_error_handler(falcon.HTTPError, custom_error_handler)

        # add media handlers
        self._add_media_handlers()

    @property
    def _middleware(self) -> list:
        """Return the Falcon middleware."""
        return [
            TcExMiddleware(self.inputs.model, self.tcex),
            DbMiddleware(),
            ErrorMiddleware(),
            ValidationMiddleware(),
        ]

    def api_event_callback(self, environ, response_handler):
        """Create the API"""
        if not environ['PATH_INFO'].startswith('/'):
            environ['PATH_INFO'] = '/' + environ['PATH_INFO']

        with request_fork_lock:
            return self.app(environ, response_handler)
