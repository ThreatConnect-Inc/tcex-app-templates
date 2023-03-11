"""App Inputs"""
# standard library
from typing import Annotated

# third-party
from pydantic import BaseModel
from tcex.input.field_type import String, integer, string
from tcex.input.input import Input
from tcex.input.model.app_playbook_model import AppPlaybookModel


class AppBaseModel(AppPlaybookModel):
    """Base model for the App containing any common inputs."""

    # playbookDataType = String, StringArray
    input_string: list[String]
    tc_action: String


class Append(AppBaseModel):
    """Action Model"""

    # playbookDataType = String
    append_chars: Annotated[str, string(min_length=1)]


class Prepend(AppBaseModel):
    """Action Model"""

    # playbookDataType = String
    prepend_chars: Annotated[str, string(min_length=1)]


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

    def get_model(self, tc_action: str | None = None) -> type[BaseModel]:
        """Return the model based on the current action."""
        tc_action = tc_action or self.inputs.model_unresolved.tc_action  # type: ignore
        action_model_map: dict[str, type[BaseModel]] = {
            'append': Append,
            'prepend': Prepend,
            'starts_with': StartsWith,
        }

        action_model = action_model_map.get(tc_action)
        if action_model is None:
            # pylint: disable=broad-exception-raised
            raise RuntimeError(
                f'No model found for action: {self.inputs.tc_action}'  # type: ignore
            )

        return action_model_map[tc_action]

    def update_inputs(self) -> None:
        """Add custom App models to inputs.

        Input will be validate when the model is added an any exceptions will
        cause the App to exit with a status code of 1.
        """
        self.inputs.add_model(self.get_model())
