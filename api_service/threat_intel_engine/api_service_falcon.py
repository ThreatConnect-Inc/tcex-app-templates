"""ThreatConnect API Service Falcon API"""
# standard library
import itertools
import json
import logging
import os
import threading
from datetime import datetime
from functools import partial

# third-party
import arrow
import falcon
from api import custom_error_handler
from api.middleware import DbMiddleware, ErrorMiddleware, TcExMiddleware, ValidationMiddleware
from tcex import TraceLogger
from tcex.backports import cached_property

# first-party
from api_service_app import ApiServiceApp

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
        self.log: 'TraceLogger' = logger

    def build_falcon_app(self):
        """Construct a new falcon app.

        Note: this method is called for each request and should *not* re-use app objects unless
        the app object (and all of its dependencies) is thread safe.
        """
        app = falcon.App(middleware=self._middleware, sink_before_static_route=True)
        # configure app
        self._configure_app(app)
        return app

    @staticmethod
    def _add_media_handlers(app):
        """Add API handlers."""
        json_handler = falcon.media.JSONHandler(
            dumps=partial(json.dumps, cls=DatetimeEncoder),
        )
        extra_handlers = {
            'application/json': json_handler,
        }
        app.req_options.media_handlers.update(extra_handlers)  # pylint: disable=no-member
        app.resp_options.media_handlers.update(extra_handlers)  # pylint: disable=no-member

    def _add_redirect_and_sink(self, app):
        """Add redirect and sink to angular App."""
        # serve index.html specifically since `/` will not match a file (fallback returned)
        # index.html then calls ng route which will redirect to ui/dashboard
        app.add_static_route('/', self._ui_files, fallback_filename='index.html')

        # add routing sinks for "/ui/*", if this path is hit it indicates that
        # ng was already loaded and someone is trying to reload the page. this is
        # not technically supported, but we will redirect to the dashboard.
        self._add_routing_sinks(app)

    @staticmethod
    def _add_routing_sinks(app):
        """Add routing sinks to redirect all request to the UI."""

        def _ng_redirect(req: 'falcon.Request', _resp: 'falcon.Response'):
            """Redirect to angular index.html file."""
            path_count = req.path.count('/') - 1
            redirect = '/'.join(['..'] * path_count)
            raise falcon.HTTPPermanentRedirect(redirect)

        app.add_sink(_ng_redirect, prefix='/ui')

    def _configure_app(self, app):
        """Configure the Falcon App."""
        app.req_options.auto_parse_qs_csv = True  # auto parse csv parameters
        app.req_options.strip_url_path_trailing_slash = True
        self._add_redirect_and_sink(app)

        # add custom error handler for api
        app.add_error_handler(falcon.HTTPError, custom_error_handler)

        # add media handlers
        self._add_media_handlers(app)

    @property
    def _middleware(self) -> list:
        """Return the Falcon middleware."""
        return [
            TcExMiddleware(self.inputs.model, self.tcex),
            DbMiddleware(),
            ErrorMiddleware(),
            ValidationMiddleware(),
        ]

    @cached_property
    def app_pool(self):
        """Create a pool of WSGI objects to handle requests."""
        return itertools.cycle([(threading.Lock(), self.build_falcon_app()) for _ in range(6)])

    def api_event_callback(self, environ, response_handler):
        """Create the API"""
        lock, app = next(self.app_pool)

        # iterate through the app pool until we get an available app
        while not lock.acquire(blocking=False):
            lock, app = next(self.app_pool)
        try:
            self.log.trace(f'feature=api-service, event=event-callback, app={id(app)}')
            if not environ['PATH_INFO'].startswith('/'):
                environ['PATH_INFO'] = '/' + environ['PATH_INFO']

            return app(environ, response_handler)
        finally:
            lock.release()
