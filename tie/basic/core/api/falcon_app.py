"""Falcon Response Class"""

import json
from functools import partial
from pathlib import Path

import falcon
from falcon import media

from core.api.error.custom_error_handler import custom_error_handler
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.util.custom_handler import CustomHandler


class FalconApp(falcon.App):
    """New Falcon Response class."""

    def __init__(self, *args, **kwargs):
        """Initialize Falcon App."""
        super().__init__(*args, **kwargs)

        # update the request and response types
        self._request_type = FalconRequest
        self._response_type = FalconResponse

        # configure app
        self.req_options.auto_parse_qs_csv = True  # auto parse csv parameters
        self.req_options.strip_url_path_trailing_slash = True
        self._add_redirect_and_sink()

        # add custom error handler for api
        self.add_error_handler(falcon.HTTPError, custom_error_handler)

        # add media handlers
        self._add_media_handlers()

    def _add_media_handlers(self):
        """Add API handlers."""
        json_handler = media.JSONHandler(dumps=partial(json.dumps, cls=CustomHandler))
        extra_handlers = {'application/json': json_handler}
        self.resp_options.media_handlers.update(extra_handlers)

    def _add_redirect_and_sink(self):
        """Add redirect and sink to angular App."""
        if self.ui_files.exists():
            # serve index.html specifically since `/` will not match a file (fallback returned)
            # index.html then calls ng route which will redirect to ui/dashboard
            self.add_static_route('/', self.ui_files, fallback_filename='index.html')

            # add routing sinks for "/ui/*", if this path is hit it indicates that
            # ng was already loaded and someone is trying to reload the page. this is
            # not technically supported, but we will redirect to the dashboard.
            self._add_routing_sinks()

    def _add_routing_sinks(self):
        """Add routing sinks to redirect all request to the UI."""

        def _ng_redirect(req: FalconRequest, _resp: FalconResponse):
            """Redirect to angular index.html file."""
            path_count = req.path.count('/') - 1
            redirect = '/'.join(['..'] * path_count)
            raise falcon.HTTPPermanentRedirect(redirect)

        self.add_sink(_ng_redirect, prefix='/ui')  # type: ignore

    @property
    def ui_files(self):
        """Return the UI files."""
        return Path.cwd() / 'ui_build' / 'browser'
