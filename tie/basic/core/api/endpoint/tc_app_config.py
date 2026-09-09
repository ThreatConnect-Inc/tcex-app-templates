"""Class for /api/tc/app-config endpoint"""

from typing import Any

from pydantic import Extra
from spectree import Response

from core.api.endpoint.endpoint_base_abc import EndpointBaseABC
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_settings
from core.api.validation.models.query_param_filter_model import QueryParamFilterModel
from core.model.tie.item_model import ItemModel

try:
    from api.ui_config_builder import UIConfigBuilder
except ImportError:
    UIConfigBuilder = None


class FieldLabelModel(ItemModel, extra=Extra.allow):
    """Field Label Model"""

    field: str
    label: str


class FormModel(ItemModel, extra=Extra.allow):
    """Form Model"""

    choices: list[str] | None
    default: str | list[str] | None
    info: str | None
    label: str
    minWidth: int | None  # noqa: N815
    name: str
    type: str | None
    validators: list


class FieldsModel(ItemModel, extra=Extra.allow):
    """Fields Model"""

    fields: list[FormModel]


class ValidatorModel(ItemModel, extra=Extra.allow):
    """Validator Model"""

    config: Any
    name: str


class AdhocRequestModel(ItemModel, extra=Extra.allow):
    """Adhoc Request Model"""

    form: FieldsModel


class DownloadTiModel(ItemModel, extra=Extra.allow):
    """Download TI Model"""

    form: FieldsModel


class JobTableModel(ItemModel, extra=Extra.allow):
    """Job Table Model"""

    columns: list[FieldLabelModel]
    details: list[FieldLabelModel]
    filters: FieldsModel


class UiModel(ItemModel, extra=Extra.allow):
    """UI Model"""

    adhocRequest: AdhocRequestModel | None = None  # noqa: N815
    downloadTI: DownloadTiModel | None = None  # noqa: N815
    jobTable: JobTableModel | None = None  # noqa: N815
    owner: str
    title: str
    version: str


class AppConfig(ItemModel, extra=Extra.allow):
    """App Config Model"""

    schema_version: str
    ui: UiModel


class TcAppConfig(EndpointBaseABC):
    """Class for /api/tc/app-config endpoint"""

    @spec.validate(
        query=QueryParamFilterModel,
        resp=Response(HTTP_200=AppConfig),
        skip_validation=True,
        tags=[tag_settings],
    )
    def on_get(
        self,
        _req: FalconRequest,
        resp: FalconResponse,
        query_params: QueryParamFilterModel,
    ):
        """Get the UI configuration for the App."""
        ui_config = {}
        brand = 'threatconnect'

        if UIConfigBuilder:
            ui_config_builder = UIConfigBuilder(self)
            ui_config = ui_config_builder.populate()
            brand = ui_config_builder.brand()

        resp_media = {
            'schema_version': '1.0.0',
            'ui': {
                'title': str(self.tcex.app.ij.model.display_name),
                'version': str(self.tcex.app.ij.model.program_version),
                'owner': self.settings.tc_owner,
                'brand': brand,
                **ui_config,
            },
        }
        resp.media = resp.response_model(resp_media, AppConfig, query_params)
