"""Class for /api/report/pdf-tracker endpoint"""
# standard library
from typing import List, Optional

# third-party
import falcon
from pydantic import Field
from sqlalchemy.orm import Query

# first-party
from api.resource_abc import ResourceABC
from model import FilterParamPaginatedModel, ReportPdfTrackerModel
from schema import ReportPdfTrackerSchema


class GetQueryParamModel(FilterParamPaginatedModel):
    """Params Model"""

    id_: Optional[str] = Field(None, alias='id', description='Filter by Report ID.')


# pylint: disable=unused-argument
class ReportPdfTrackerResource(ResourceABC):
    """Class for /api/report/pdf-tracker endpoint"""

    validation_models = {
        'GET': {
            'request': {
                'query_params': GetQueryParamModel,
            }
        }
    }

    def _db_query_get(
        self,
        id_: Optional[str],
    ) -> Query:
        """Return DB query."""
        query = self.session.query(ReportPdfTrackerSchema)

        # filter on request id
        if id_ is not None:
            query = query.filter(ReportPdfTrackerSchema.id == id_)

        return query

    def _db_result_get(self, query: Query) -> List[ReportPdfTrackerSchema]:
        """Return DB records."""
        return self._db_get_record(
            query, 'all', 'Unexpected error occurred while retrieving Batch Errors.'
        )

    def on_get(self, req: falcon.Request, resp: falcon.Response):
        """Handle GET requests."""
        query = self._db_query_get(req.context.params.id_)

        # paginator
        sort = self._db_sort(req.context.params, ReportPdfTrackerSchema, default_sort='id')
        paginator = self._db_paginator(query, req, sort)

        # generate and return the response
        resp.media = self.response_media(
            req,
            self._db_result_get(paginator.query),
            ReportPdfTrackerModel,
            req.context.params,
            paginator,
        )
