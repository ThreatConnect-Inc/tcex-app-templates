"""View for ThreatConnect Search Results.

isort:skip_file
"""
# standard library
from itertools import islice
from typing import TYPE_CHECKING

# third-party
from flask import render_template, request
from flask.views import View

if TYPE_CHECKING:
    # third-party
    from tcex import TcEx


class TCSearchView(View):
    """View class for TC Indicator Search results."""

    methods = ['POST']

    page_size = 10

    def __init__(self, tcex: 'TcEx') -> None:
        """."""
        super().__init__()
        self.tcex = tcex

    def dispatch_request(self):
        """Search ThreatConnect with the given parameters."""
        tql_query = request.form.get('tqlQuery')
        attributes = bool(request.form.get('attributes'))
        result_limit = int(request.form.get('resultLimit', self.page_size))
        result_start = int(request.form.get('resultStart', 0))

        params = {
            'tql_query': tql_query,
            'attributes': attributes,
            'result_limit': result_limit,
            'result_start': result_start + result_limit,
        }

        fields = []

        if attributes:
            fields.append('attributes')

        indicators = self.tcex.api.tc.v3.indicators(
            params={
                'resultLimit': result_limit,
                'resultStart': result_start,
                'sort': 'dateModified DESC',
                'fields': fields,
            }
        )

        indicators.filter.tql = tql_query

        # use islice here to stop auto-pagination.
        results = [i.model for i in islice(indicators, result_limit)]

        return render_template('results.html.jinja', **params, results=results)
