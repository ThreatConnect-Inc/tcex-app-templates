"""ThreatConnect API Service App"""

# third-party
from flask_app import create_app
from wsgi_types import WSGIApplication

# first-party
from api_service_app import ApiServiceApp


class App(ApiServiceApp):
    """API Service App"""

    def get_wsgi_app(self, url_prefix: str) -> WSGIApplication:
        """Create and return Flask app."""
        return create_app(url_prefix, self.tcex, self.inputs)
