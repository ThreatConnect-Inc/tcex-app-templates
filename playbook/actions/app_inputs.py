"""App Inputs"""
# standard library
from typing import Annotated

# third-party
from pydantic import BaseModel, validator
from tcex.input.field_type import String, always_array, integer, string
from tcex.input.input import Input
from tcex.input.model.app_playbook_model import AppPlaybookModel


class AppBaseModel(AppPlaybookModel):
    """Base model for the App containing any common inputs."""

    # playbookDataType = String, StringArray
    input_string: list[String]
    tc_action: String

    # the App takes both String and StringArray as input, ensure that the input
    # is always an array. splitting the value on a comma is also supported.
    _always_array = validator('input_string', allow_reuse=True, pre=True)(
        always_array(split_csv=True)
    )


class Append(AppBaseModel):
    """Action Model"""

    # playbookDataType = String
    append_chars: Annotated[str, string(min_length=1)]


class Capitalize(AppBaseModel):
    """Action Model"""


class LowerCase(AppBaseModel):
    """Action Model"""


class Prepend(AppBaseModel):
    """Action Model"""

    # playbookDataType = String
    prepend_chars: Annotated[str, string(min_length=1)]


class Reverse(AppBaseModel):
    """Action Model"""


class StartsWith(AppBaseModel):
    """Action Model"""

    # playbookDataType = String
    starts_with_chars: Annotated[str, string(min_length=1)]
    # playbookDataType = String
    starts_with_start: Annotated[int, integer(gt=-1)]
    # playbookDataType = String
    starts_with_stop: Annotated[int, integer(gt=0)] | None


class AppInputs:
    """App Inputs"""

    def __init__(self, inputs: Input) -> None:
        """Initialize class properties."""
        self.inputs = inputs

    def action_model_map(self, tc_action: str) -> type[BaseModel]:
        """Return action model map."""
        _action_model_map = {
            'Append': Append,
            'capitalize': Capitalize,
            'lowercase': LowerCase,
            'prepend': Prepend,
            'reverse': Reverse,
            'starts_with': StartsWith,
        }
        tc_action_key = tc_action.lower().replace(' ', '_')
        return _action_model_map.get(tc_action_key)

    def get_model(self, tc_action: str | None = None) -> type[BaseModel]:
        """Return the model based on the current action."""
        tc_action = tc_action or self.inputs.model_unresolved.tc_action  # type: ignore
        if tc_action is None:
            raise RuntimeError('No action (tc_action) found in inputs.')

        action_model = self.action_model_map(tc_action.lower())
        if action_model is None:
            # pylint: disable=broad-exception-raised
            raise RuntimeError(
                'No model found for action: '
                f'{self.inputs.model_unresolved.tc_action}'  # type: ignore
            )

        return action_model

    def update_inputs(self) -> None:
        """Add custom App models to inputs.

        Input will be validate when the model is added an any exceptions will
        cause the App to exit with a status code of 1.
        """
        self.inputs.add_model(self.get_model())
