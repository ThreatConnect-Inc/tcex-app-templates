"""Class for /api/download/falcon-ti endpoint"""

import falcon
from pydantic import Field, field_validator
from spectree import Response

from core.api.endpoint.endpoint_base_abc import EndpointBaseABC
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_download
from core.api.validation.models.query_param_filter_model import QueryParamFilterModel
from core.api.validation.models.query_param_model import param_to_list
from core.model.model_base import ModelBase
from more.transform.sample_transform import SampleTransform


class GetQueryParamModel(QueryParamFilterModel):
    """Params Model"""

    ids: list[str] = Field(..., description='One or more ID to retrieve.')
    type: str = Field(..., description='The type of object to retrieve.')
    # convert params with multiple value (e.g., ?id=1,id=2)
    # and/or csv delimited (e.g., id=1,2) into a list.
    _ids_to_list = field_validator('ids', mode='before')(param_to_list)


class UploadRequestBody(ModelBase):
    """Request body model."""

    data: dict


class DownloadTiResource(EndpointBaseABC):
    """Class for /api/download/ti endpoint"""

    @spec.validate(
        query=GetQueryParamModel,
        resp=Response('HTTP_200'),
        skip_validation=True,
        tags=[tag_download],
    )
    def on_get(
        self,
        _req: FalconRequest,
        resp: FalconResponse,
        query_params: GetQueryParamModel,
    ):
        """Download and convert to TC batch schema."""
        responses = []

        match query_params.type.lower():
            case 'event':
                transform = [SampleTransform(self.settings, self.tcex).transform]
            case _:
                msg = 'Invalid type'
                raise falcon.HTTPBadRequest(msg, f'Invalid type: {query_params.type}')

        for id_ in query_params.ids:
            try:
                # self.sdk.get(type=query_params.type, id=id_)
                responses.append({'id': id_, 'ip': '1.1.1.1'})
            except Exception:
                self.log.exception(f'action=get-details, id={id_}')

        transformed = self.tcex.api.tc.ti_transforms(responses, transform).batch

        resp.media = {'original': responses, 'transformed': transformed}

    @spec.validate(
        query=GetQueryParamModel,
        resp=Response('HTTP_200'),
        skip_validation=True,
        tags=[tag_download],
    )
    def on_post(
        self,
        _req: FalconRequest,
        _resp: FalconResponse,
        body: UploadRequestBody,
    ):
        """Send data to ThreatConnect for ingesting."""
        self.create_ti_batch(body.data)

    def create_ti_batch(self, batch_data: dict):
        """Submit batch data."""
        batch = self.tcex.api.tc.v2.batch(owner=self.settings.tc_owner)
        batch_response = batch.submit_create_and_upload(batch_data)
        self.log.debug(f'batch_response: {batch_response}')
