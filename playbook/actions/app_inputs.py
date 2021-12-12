"""App Inputs"""
# standard library
from typing import Optional

# third-party
from pydantic import BaseModel, PositiveInt
from pydantic.types import constr
from tcex.input.field_types.string_array import StringArray


class AppBaseModel(BaseModel):
    """Base model for the App containing any common inputs."""

    # playbookDataType = String, StringArray
    input_string: StringArray
    tc_action: str


class Append(AppBaseModel):
    """Action Model"""

    # playbookDataType = String
    append_chars: constr(min_length=1)


class Prepend(AppBaseModel):
    """Action Model"""

    # playbookDataType = String
    prepend_chars: constr(min_length=1)


class StartsWith(AppBaseModel):
    """Action Model"""

    # playbookDataType = String
    starts_with_chars: constr(min_length=1)
    # playbookDataType = String
    starts_with_start: PositiveInt = 0
    # playbookDataType = String
    starts_with_stop: Optional[PositiveInt]


class AppInputs:
    """App Inputs"""

    def __init__(self, inputs: 'BaseModel') -> None:
        """Initialize class properties."""
        self.inputs = inputs

        # update with custom models and run validation
        self.update_inputs()

    def update_inputs(self) -> None:
        """Add custom App models to inputs.

        Input will be validate when the model is added an any exceptions will
        cause the App to exit with a status code of 1.
        """
        action_model_map = {
            'append': Append,
            'prepend': Prepend,
            'starts_with': StartsWith,
        }
        self.inputs.add_model(action_model_map.get(self.inputs.model_unresolved.tc_action))
