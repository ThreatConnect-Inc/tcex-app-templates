"""ThreatConnect API Service App"""
# standard library
from wsgiref.types import WSGIApplication

# first-party
from api_service_app import ApiServiceApp
from flask_app import create_app


class App(ApiServiceApp):
    """API Service App"""

    def get_wsgi_app(self) -> WSGIApplication:
        """Create and return Flask app."""
        return create_app(self.tcex)
