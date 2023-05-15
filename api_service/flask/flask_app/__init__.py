"""Create and configure Flask app."""
# third-party
from flask import Flask
from tcex import TcEx

# first-party
from flask_app.tc_search_blueprint import create_blueprint as create_tc_search_blueprint

__all__ = ['create_app']


def create_app(tcex: TcEx):
    """Create and configure Flask app."""

    app = Flask(__name__)

    app.url_map.strict_slashes = False

    # note the url_prefix, we want to make sure our app is properly aware of its full URL.
    app.register_blueprint(create_tc_search_blueprint(tcex))

    return app
