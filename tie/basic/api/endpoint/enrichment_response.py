"""."""

from spectree.response import Response

from core.api.endpoint.endpoint_base_abc import EndpointBaseABC
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_service
from core.api.validation.models.query_param_filter_model import QueryParamFilterModel
from core.message_service.model.tcva.enrichment_request_model import (
    EnrichmentRequestModel,
)
from core.message_service.model.tcva.enrichment_response_model import (
    EnrichmentResponseModel,
)


class GetQueryParamModel(QueryParamFilterModel):
    """."""


class EnrichmentResponse(EndpointBaseABC):
    """."""

    def __init__(self, message_handler):
        """."""
        self.message_handler = message_handler

    @spec.validate(
        json=EnrichmentRequestModel,
        query=GetQueryParamModel,
        resp=Response(HTTP_200=EnrichmentResponseModel),
        skip_validation=True,
        tags=[tag_service],
    )
    def on_post(
        self,
        _req: FalconRequest,
        resp: FalconResponse,
        body: EnrichmentRequestModel,
        query_params: GetQueryParamModel,
    ):
        """."""
        resp.media = self.message_handler.on_post(body)
        if resp.media:
            resp.media = resp.response_model(
                resp.media,
                EnrichmentResponseModel,
                query_params,
            )
