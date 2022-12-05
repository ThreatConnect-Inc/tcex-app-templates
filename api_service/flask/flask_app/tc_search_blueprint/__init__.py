"""Blueprint module for a rudimentary TC indicator search.

Note: this is demo code only.
"""
# standard library
from typing import TYPE_CHECKING

# third-party
from flask import Blueprint, render_template
from flask_app.tc_search_blueprint.tc_search_view import TCSearchView

if TYPE_CHECKING:
    # third-party
    from tcex import TcEx

__all__ = ['create_blueprint']


def create_blueprint(tcex: 'TcEx'):
    """Create the TC Search blueprint.

    Blueprints are modular components for a flask app, see:
    https://flask.palletsprojects.com/en/2.2.x/blueprints/
    """

    bp = Blueprint(
        'tc_search',
        __name__,
        static_url_path='/static',
        static_folder='static',
        template_folder='templates',
    )

    bp.add_url_rule('/search', view_func=TCSearchView.as_view('search', tcex=tcex))

    @bp.route('/')
    def tc_search_form():
        """Just serve template for the TC search form."""
        return render_template('index.html.jinja')

    return bp
