"""Class for /api/report/batch-error endpoint"""
# standard library
from typing import List, Optional

# third-party
import falcon
from pydantic import Field
from sqlalchemy.orm import Query

# first-party
from api.resource_abc import ResourceABC
from model import BatchErrorModel, FilterParamPaginatedModel
from schema import BatchErrorSchema


class GetQueryParamModel(FilterParamPaginatedModel):
    """Params Model"""

    request_id: Optional[str] = Field(None, description='Filter by Request ID.')


# pylint: disable=unused-argument
class ReportBatchErrorResource(ResourceABC):
    """Class for /api/report/batch-error endpoint"""

    validation_models = {
        'GET': {
            'request': {
                'query_params': GetQueryParamModel,
            }
        }
    }

    def _db_query_get(
        self,
        request_id: Optional[str],
    ) -> Query:
        """Return DB query."""
        query = self.session.query(BatchErrorSchema)

        # filter on request id
        if request_id is not None:
            query = query.filter(BatchErrorSchema.request_id.ilike(f'%{request_id}%'))

        return query

    def _db_result_get(self, query: Query) -> List[BatchErrorSchema]:
        """Return DB records."""
        return self._db_get_record(
            query, 'all', 'Unexpected error occurred while retrieving Batch Errors.'
        )

    def on_get(self, req: falcon.Request, resp: falcon.Response):
        """Handle GET requests."""
        query = self._db_query_get(req.context.params.request_id)

        # paginator
        sort = self._db_sort(req.context.params, BatchErrorSchema, default_sort='id')
        paginator = self._db_paginator(query, req, sort)

        # generate and return the response
        resp.media = self.response_media(
            req,
            self._db_result_get(paginator.query),
            BatchErrorModel,
            req.context.params,
            paginator,
        )
