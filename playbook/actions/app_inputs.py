"""App Inputs"""
# standard library
from typing import List, Optional

# third-party
from pydantic import BaseModel
from tcex.input.field_types import String, integer, string


class AppBaseModel(BaseModel):
    """Base model for the App containing any common inputs."""

    # playbookDataType = String, StringArray
    input_string: List[String]
    tc_action: String


class Append(AppBaseModel):
    """Action Model"""

    # playbookDataType = String
    append_chars: string(min_length=1)


class Prepend(AppBaseModel):
    """Action Model"""

    # playbookDataType = String
    prepend_chars: string(min_length=1)


class StartsWith(AppBaseModel):
    """Action Model"""

    # playbookDataType = String
    starts_with_chars: string(min_length=1)
    # playbookDataType = String
    starts_with_start: integer(gt=-1)
    # playbookDataType = String
    starts_with_stop: Optional[integer(gt=0)]


class AppInputs:
    """App Inputs"""

    def __init__(self, inputs: 'BaseModel') -> None:
        """Initialize class properties."""
        self.inputs = inputs

    def get_model(self, tc_action: Optional[str] = None) -> 'BaseModel':
        """Return the model based on the current action."""
        tc_action = tc_action or self.inputs.model_unresolved.tc_action
        action_model_map = {
            'append': Append,
            'prepend': Prepend,
            'starts_with': StartsWith,
        }
        return action_model_map.get(tc_action)

    def update_inputs(self) -> None:
        """Add custom App models to inputs.

        Input will be validate when the model is added an any exceptions will
        cause the App to exit with a status code of 1.
        """
        self.inputs.add_model(self.get_model())
