"""Create and configure Flask app."""
# standard library
from typing import TYPE_CHECKING

# third-party
from flask import Flask

# first-party
from flask_app.tc_search_blueprint import create_blueprint as create_tc_search_blueprint

if TYPE_CHECKING:
    # third-party
    from tcex import TcEx
    from tcex.input.input import Input

__all__ = ['create_app']


def create_app(url_prefix, tcex: 'TcEx', inputs: 'Input'):  # pylint: disable=unused-argument
    """Create and configure Flask app."""

    app = Flask(__name__)

    # this helps url_for() correctly generate urls with our prefix.
    if url_prefix:
        app.config['APPLICATION_ROOT'] = url_prefix

    app.url_map.strict_slashes = False

    # note the url_prefix, we want to make sure our app is properly aware of its full URL.
    app.register_blueprint(create_tc_search_blueprint(tcex), url_prefix=url_prefix)

    return app
