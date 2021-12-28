"""App Inputs"""
# third-party
from pydantic import BaseModel
from tcex.input.field_types import String


class AppBaseModel(BaseModel):
    """Base model for the App containing any common inputs."""

    tc_owner: String


class AppInputs:
    """App Inputs"""

    def __init__(self, inputs: BaseModel) -> None:
        """Initialize class properties."""
        self.inputs = inputs

    def update_inputs(self) -> None:
        """Add custom App models to inputs. Validation will run at the same time."""
        self.inputs.add_model(AppBaseModel)
