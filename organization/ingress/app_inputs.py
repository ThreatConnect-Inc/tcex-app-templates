"""App Inputs"""
# third-party
from pydantic import BaseModel


class AppBaseModel(BaseModel):
    """Base model for the App containing any common inputs."""

    tc_owner: str


class AppInputs:
    """App Inputs"""

    def __init__(self, inputs: BaseModel) -> None:
        """Initialize class properties."""
        self.inputs = inputs
        self.update_inputs()

    def update_inputs(self) -> None:
        """Add custom App models to inputs. Validation will run at the same time."""
        self.inputs.add_model(AppBaseModel)
