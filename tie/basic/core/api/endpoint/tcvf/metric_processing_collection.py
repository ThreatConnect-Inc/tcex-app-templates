"""Class for /api/metric/processing endpoint"""

from functools import cached_property

from spectree import Response

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_metric
from core.api.validation.models.query_param_filter_pagination_model import (
    QueryParamFilterPaginationModel,
)
from core.json_db.dao import JsonDBDAO
from core.model.tie import (
    TiProcessingMetricModel,
    TiProcessingMetricPaginatedResponseModel,
)


class MetricProcessingCollection(EndpointBase):
    """Class for /api/metric/processing endpoint"""

    @cached_property
    def dao(self) -> JsonDBDAO[TiProcessingMetricModel]:
        """Return the dao."""
        return JsonDBDAO(self.db, TiProcessingMetricModel)

    @spec.validate(
        query=QueryParamFilterPaginationModel,
        resp=Response(HTTP_200=TiProcessingMetricPaginatedResponseModel),
        skip_validation=True,
        tags=[tag_metric],
    )
    def on_get(
        self,
        _req: FalconRequest,
        resp: FalconResponse,
        query_params: QueryParamFilterPaginationModel,
    ):
        """Get metric data related to counts."""
        resp_data = self.dao.get_page_for_query_params(
            query_params=query_params,
        )
        resp.media = resp.response_model(
            resp_data, TiProcessingMetricPaginatedResponseModel, query_params
        )
