"""Class for /api/report/batch-error endpoint"""

from functools import cached_property

from pydantic.fields import Field
from spectree import Response

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_job
from core.api.validation.models.query_param_filter_model import QueryParamFilterModel
from core.dao.batch_error_dao import BatchErrorDAO
from core.model.model_base import ModelBase
from core.model.response.response_model import ResponseModel


class GetQueryParamModel(QueryParamFilterModel):
    """Params Model"""

    request_id: str | None = Field(None, description='Filter by Request ID.')


class BatchErrorCountModel(ModelBase):
    """Model for Batch Error Count"""

    count: int
    error: str
    code: str


class BatchErrorCountsResponseModel(ResponseModel):
    """Response Model"""

    data: list[BatchErrorCountModel]


class BatchErrorCountsCollection(EndpointBase):
    """Class for /api/report/batch-error endpoint"""

    @cached_property
    def dao(self):
        """."""
        return BatchErrorDAO(self.db)

    @spec.validate(
        query=GetQueryParamModel,
        resp=Response(HTTP_200=BatchErrorCountsResponseModel),
        skip_validation=True,
        tags=[tag_job],
    )
    def on_get(
        self,
        req: FalconRequest,  # noqa: ARG002
        resp: FalconResponse,
        query_params: GetQueryParamModel,
    ):
        """Return batch error counts by error code."""
        resp.media = resp.response_model(
            {'data': self.dao.get_error_counts_by_code(query_params.request_id)},
            BatchErrorCountsResponseModel,
            query_params,
        )
