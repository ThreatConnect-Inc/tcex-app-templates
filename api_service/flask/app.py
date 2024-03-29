"""ThreatConnect API Service App"""
# standard library
from typing import TYPE_CHECKING

# third-party
from flask_app import create_app

# first-party
from api_service_app import ApiServiceApp

if TYPE_CHECKING:
    # third-party
    from wsgi_types import WSGIApplication


class App(ApiServiceApp):
    """API Service App"""

    def get_wsgi_app(self, url_prefix: str) -> 'WSGIApplication':
        """Create and return Flask app."""
        return create_app(url_prefix, self.tcex, self.inputs)
