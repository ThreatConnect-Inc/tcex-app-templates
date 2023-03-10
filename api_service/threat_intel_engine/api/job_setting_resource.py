"""Class for /api/1.0/job/setting endpoint"""
# third-party
import falcon
from api.resource_abc import ResourceABC
from model import FilterParamPaginatedModel


# pylint: disable=unused-argument
class JobSettingResource(ResourceABC):
    """Class for /api/1.0/job/setting endpoint"""

    validation_models = {
        'GET': {
            'request': {
                'query_params': FilterParamPaginatedModel,
            }
        },
    }

    def on_get(self, _req: falcon.Request, resp: falcon.Response):
        """Handle POST requests."""
        resp.media = {
            'tql': self.settings.tql,
            'owner': self.settings.external_owner,
        }
