"""Class for /api/report/batch-error endpoint"""

from functools import cached_property

from pydantic import Field, validator
from spectree import Response

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_job
from core.api.validation.models.query_param_filter_pagination_model import (
    QueryParamFilterPaginationModel,
)
from core.dao.batch_error_dao import BatchErrorDAO
from core.json_db import SortBy, where
from core.model.tie import BatchErrorPaginatedResponseModel


class GetQueryParamModel(QueryParamFilterPaginationModel, where.ToWhere):
    """Params Model"""

    error_code: str | None = Field(None, description='Filter by error code.')
    request_id: str | None = Field(None, description='Filter by Request ID.')
    messages: list[str] | None = Field(None, description='Filter by messages.')
    reason: str | None = Field(None, description='Filter by reason.')

    def to_where(self) -> where.WhereDict:
        """Convert the object to a where dictionary that can be passed to DAO objects."""
        return {
            'message': where.is_in(self.messages),
            'reason': where.contains(self.reason),
        }

    @validator('messages', always=True, pre=True)
    def _messages(cls, v):
        """Validate error_codes value."""
        match v:
            case str():
                return [f.strip() for f in v.split(',')]
            case _:
                return v

    @validator('sort', always=True, pre=True)
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


class BatchErrorCollection(EndpointBase):
    """Class for /api/report/batch-error endpoint"""

    @cached_property
    def dao(self):
        """Return a new instance of the DAO."""
        return BatchErrorDAO(self.db)

    @spec.validate(
        query=GetQueryParamModel,
        resp=Response(HTTP_200=BatchErrorPaginatedResponseModel),
        skip_validation=True,
        tags=[tag_job],
    )
    def on_get(
        self,
        req: FalconRequest,  # noqa: ARG002
        resp: FalconResponse,
        query_params: GetQueryParamModel,
    ):
        """Return batch errors from job requests."""
        resp_data = self.dao.get_page_for_query_params(
            query_params,
            request_id=query_params.request_id,
            error_code=query_params.error_code,
        )
        resp.media = resp.response_model(resp_data, BatchErrorPaginatedResponseModel, query_params)
