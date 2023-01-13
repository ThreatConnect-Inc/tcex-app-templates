"""Class for /api/download/falcon-ti endpoint"""
# standard library
import traceback
from typing import TYPE_CHECKING, List

# third-party
import falcon
from pydantic import Field, validator

# first-party
from api.resource_abc import ResourceABC
from model import FilterParamModel, param_to_list
from more.transforms import IndicatorTransform

if TYPE_CHECKING:
    # first-party
    from more.transforms.transform_abc import TransformABC


class GetQueryParamModel(FilterParamModel):
    """Params Model"""

    convert: bool = Field(False, description='Convert to TC format.')
    enrich: bool = Field(False, description='Add to ThreatConnect.')
    ids: List[str] = Field(..., description='One or more ID to retrieve.')
    type: str = Field(..., description='The TI type to retrieve.')

    # convert params with multiple value (e.g., ?id=1,id=2)
    # and/or csv delimited (e.g., id=1,2) into a list.
    _ids_to_list = validator('ids', allow_reuse=True, pre=True)(param_to_list)


class DownloadFalconTiResource(ResourceABC):
    """Class for /api/download/falcon-ti endpoint"""

    validation_models = {
        'GET': {
            'request': {
                'query_params': GetQueryParamModel,
            }
        },
    }

    def _type_mapping(self, ti_type: str) -> dict:
        """Return type mapping."""
        _mapping = {
            'indicator': {
                'convert_transform': IndicatorTransform,
                'sdk_method': self.provider_sdk.get,
            }
        }

        try:
            return _mapping[ti_type]
        except Exception as ex:
            err = self.error(
                description=f'Invalid type provided ({ti_type}).',
                exception=traceback.format_exc().split('\n'),
                title='Bad Request',
            )
            raise falcon.HTTPBadRequest(**err) from ex

    def on_get(self, req: 'falcon.Request', resp: 'falcon.Response'):
        """Handle GET requests."""
        mapping_data = self._type_mapping(req.context.params.type)
        convert_transform = mapping_data.get('convert_transform')
        sdk_method = mapping_data.get('sdk_method')

        # download the data
        data = []
        for i in req.context.params.ids:
            try:
                data.append(sdk_method(indicators=req.context.params.ids).get('data', {}))
            except Exception:
                err = self.error(
                    description='failure',
                    exception=traceback.format_exc().split('\n'),
                    title='Bad Request',
                )
                raise falcon.HTTPBadRequest(**err)

        # process results
        response_media = data

        if any([req.context.params.convert, req.context.params.enrich]):
            ti_transform: 'TransformABC' = convert_transform(
                self.settings, self.tcex
            )
            transform = self.tcex.api.tc.ti_transforms(response_media, ti_transform.transform)
            response_media = transform.batch

            # send to batch
            if req.context.params.enrich is True:
                ti_transform.create_ti_batch(response_media)

        resp.media = response_media
