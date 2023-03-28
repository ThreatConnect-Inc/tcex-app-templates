"""Class for /api/metric/processing endpoint"""

# third-party
import falcon
from model import FilterParamPaginatedModel, TiProcessingMetricModel
from schema import TiProcessingMetricSchema
from sqlalchemy.orm import Query

from .resource_abc import ResourceABC


# pylint: disable=unused-argument
class MetricProcessingResource(ResourceABC):
    """Class for /api/metric/processing endpoint"""

    validation_models = {
        'GET': {
            'request': {
                'query_params': FilterParamPaginatedModel,
            }
        },
    }

    def _db_query_get(self) -> Query:
        """Return DB query."""
        return self.session.query(TiProcessingMetricSchema)

    def _db_result_get(self, query: Query) -> list[TiProcessingMetricSchema]:
        """Return DB records."""
        return self._db_get_record(
            query, 'all', 'Unexpected error occurred while retrieving metrics.'
        )

    def on_get(self, req: falcon.Request, resp: falcon.Response):
        """Handle GET requests."""
        query = self._db_query_get()

        # paginator
        sort = self._db_sort(req.context.params, TiProcessingMetricSchema, default_sort='id')
        paginator = self._db_paginator(query, req, sort)

        # generate and return the response
        resp.media = self.response_media(
            req,
            self._db_result_get(paginator.query),
            TiProcessingMetricModel,
            req.context.params,
            paginator,
        )
