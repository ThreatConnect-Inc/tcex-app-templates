"""App Inputs"""
# pyright: reportGeneralTypeIssues=false

# third-party
from tcex.input.field_type import KeyValue, TCEntity
from tcex.input.input import Input
from tcex.input.model.app_playbook_model import AppPlaybookModel


class AppBaseModel(AppPlaybookModel):
    """Base model for the App containing any common inputs."""

    # pbd: String, vv: ${TEXT}
    indent: int = 4
    # pbd: KeyValue|KeyValueArray|String|StringArray|TCEntity|TCEntityArray, vv:
    # ${TEXT}
    json_data: KeyValue | list[KeyValue] | str | list[str] | TCEntity | list[TCEntity]
    sort_keys: bool = False


class AppInputs:
    """App Inputs"""

    def __init__(self, inputs: Input):
        """Initialize instance properties."""
        self.inputs = inputs

    def update_inputs(self):
        """Add custom App model to inputs.

        Input will be validate when the model is added an any exceptions will
        cause the App to exit with a status code of 1.
        """
        self.inputs.add_model(AppBaseModel)
