"""App Inputs"""
# pyright: reportGeneralTypeIssues=false

from typing import Annotated

from pydantic import BaseModel, field_validator
from tcex.app.config.install_json import InstallJson
from tcex.input.field_type import Choice, always_array, string
from tcex.input.input import Input
from tcex.input.model.app_playbook_model import AppPlaybookModel

DEFAULT_TC_ACTION = None
if _tc_action := InstallJson().model.params_dict.get('tc_action'):
    DEFAULT_TC_ACTION = _tc_action.default


class AppBaseModel(AppPlaybookModel):
    """Base model for the App containing any common inputs."""

    # pbd: String|StringArray, vv: ${TEXT}
    input_strings: Annotated[list[str], list[string(min_length=1)]]
    # vv: Capitalize|Lowercase|Reverse
    tc_action: Annotated[str, Choice] = DEFAULT_TC_ACTION

    # ensure inputs that take single and array types always return an array
    _always_array = field_validator('input_strings', mode='before')(
        always_array(allow_empty=True, include_empty=False, include_null=False, split_csv=True)
    )


class CapitalizeModel(AppBaseModel):
    """Action Model"""


class LowercaseModel(AppBaseModel):
    """Action Model"""


class ReverseModel(AppBaseModel):
    """Action Model"""


class AppInputs:
    """App Inputs"""

    def __init__(self, inputs: Input):
        """Initialize instance properties."""
        self.inputs = inputs

    def action_model_map(self, tc_action: str) -> type[BaseModel]:
        """Return action model map."""
        _action_model_map = {
            'capitalize': CapitalizeModel,
            'lowercase': LowercaseModel,
            'reverse': ReverseModel,
        }
        tc_action_key = tc_action.lower().replace(' ', '_')
        return _action_model_map.get(tc_action_key)

    def get_model(self, tc_action: str | None = None) -> type[BaseModel]:
        """Return the model based on the current action."""
        tc_action = tc_action or getattr(
            self.inputs.model_unresolved, 'tc_action', DEFAULT_TC_ACTION
        )
        if tc_action is None:
            raise RuntimeError('No action (tc_action) found in inputs.')

        action_model = self.action_model_map(tc_action.lower())
        if action_model is None:
            raise RuntimeError(
                f'No model found for action: {self.inputs.model_unresolved.tc_action}'  # type: ignore
            )

        return action_model

    def update_inputs(self):
        """Add custom App model to inputs.

        Input will be validate when the model is added an any exceptions will
        cause the App to exit with a status code of 1.
        """
        self.inputs.add_model(self.get_model())
