"""App Inputs"""
# standard library
from typing import List, Optional, Union

# third-party
from pydantic import BaseModel, validator


class AppBaseModel(BaseModel):
    """Base model for the App containing any common inputs."""

    # playbookDataType = String, StringArray
    input_string: Union[List[str], str]
    tc_action: str

    @validator('input_string', pre=True)
    def always_array(cls, v):  # pylint: disable=E0213,R0201
        """Return an array even if string provided."""
        if isinstance(v, str):
            return [v]
        return v


class ActionModelAppend(BaseModel):
    """Action Model"""

    # playbookDataType = String
    append_chars: str


class ActionModelPrepend(BaseModel):
    """Action Model"""

    # playbookDataType = String
    prepend_chars: str


class ActionModelStartsWith(BaseModel):
    """Action Model"""

    # playbookDataType = String
    starts_with_chars: str
    # playbookDataType = String
    starts_with_start: int = 0
    # playbookDataType = String
    starts_with_stop: Optional[int]


class AppInputs:
    """App Inputs"""

    def __init__(self, inputs: BaseModel) -> None:
        """Initialize class properties."""
        self.inputs = inputs
        self.update_inputs()

    def update_inputs(self) -> None:
        """Add custom App models to inputs. Validation will run at the same time."""
        models = [AppBaseModel]
        if self.inputs.tc_action == 'append':
            models.append(ActionModelAppend)
        elif self.inputs.tc_action == 'prepend':
            models.append(ActionModelPrepend)
        elif self.inputs.tc_action == 'starts_with':
            models.append(ActionModelStartsWith)
        self.inputs.add_models(models)
