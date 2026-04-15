"""."""

from pydantic import field_validator
from spectree import Response

from core.api.endpoint.endpoint_base_abc import EndpointBaseABC
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_service
from core.api.validation.models.query_param_filter_model import QueryParamFilterModel
from core.api.validation.models.query_param_model import param_to_list
from core.message_service.model.tcva.discovery_request_model import (
    DiscoveryRequestModel,
)
from core.message_service.model.tcva.discovery_response_model import (
    DiscoveryResponseModel,
)


class GetQueryParamModel(QueryParamFilterModel, DiscoveryRequestModel):  # type: ignore
    """."""

    # convert params with multiple value (e.g., ?id=1,id=2)
    # and/or csv delimited (e.g., id=1,2) into a list.
    _param_to_list = field_validator('requested_features', mode='before')(param_to_list)


class DiscoveryResponse(EndpointBaseABC):
    """."""

    def __init__(self, message_handler):
        """Initialize class properties."""
        self.message_handler = message_handler

    @spec.validate(
        query=GetQueryParamModel,
        resp=Response(HTTP_200=DiscoveryResponseModel),
        skip_validation=True,
        tags=[tag_service],
    )
    def on_get(
        self,
        _req: FalconRequest,
        resp: FalconResponse,
        query_params: GetQueryParamModel,
    ):
        """."""
        response_model = self.message_handler.on_get(query_params)

        if response_model is not None:
            resp.media = resp.response_model(
                response_model,
                DiscoveryResponseModel,
                query_params,
            )
        else:
            resp.status = 204
