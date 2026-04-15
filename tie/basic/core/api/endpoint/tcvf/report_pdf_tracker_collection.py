"""Class for /api/report/batch-error endpoint"""

from functools import cached_property

from pydantic import Field, field_validator
from spectree import Response

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_util
from core.api.validation.models.query_param_filter_pagination_model import (
    QueryParamFilterPaginationModel,
)
from core.json_db import SortBy, where
from core.json_db.dao import JsonDBDAO
from core.model.tie import ReportPdfTrackerModel, ReportPdfTrackerResponseModel


class GetQueryParamModel(QueryParamFilterPaginationModel, where.ToWhere):
    """Params Model"""

    group_id: str | None = Field(None, description='Filter by Group ID.')
    attempt_result: str | None = Field(None, description='Filter by .')

    def to_where(self) -> where.WhereDict:
        """Convert the object to a where dictionary that can be passed to DAO objects."""
        return {
            'attempt_result': where.contains(self.attempt_result),
            'group_id': where.contains(self.group_id),
        }

    @field_validator('sort')
    @classmethod
    def _sort(cls, v):
        """Validate sort value."""
        # because BatchErrorModel uses the default default_factory for Index(),
        # it's ID is a UUID7, which means it is time sortable by INDEX.
        # because of that, we can use INDEX when the sort is CREATED.
        match v.lower():
            case 'id' | 'index':
                return SortBy.INDEX
            case 'created':
                return SortBy.INDEX
            case 'modified':
                return SortBy.MODIFIED
            case _:
                return v


class ReportPDFTrackerCollection(EndpointBase):
    """Class for /api/report/pdf-tracker endpoint"""

    @cached_property
    def dao(self):
        """Return a new instance of the DAO."""
        return JsonDBDAO(self.db, ReportPdfTrackerModel)

    @spec.validate(
        query=GetQueryParamModel,
        resp=Response(HTTP_200=ReportPdfTrackerResponseModel),
        skip_validation=True,
        tags=[tag_util],
    )
    def on_get(
        self,
        _req: FalconRequest,
        resp: FalconResponse,
        query_params: GetQueryParamModel,
    ):
        """Get attachment tracker data."""
        resp_data = self.dao.get_page_for_query_params(query_params)
        resp.media = resp.response_model(resp_data, ReportPdfTrackerResponseModel, query_params)
