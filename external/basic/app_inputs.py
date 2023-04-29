"""App Inputs"""
# third-party
from pydantic import BaseModel


class AppBaseModel(BaseModel):
    """Base model for the App containing any common inputs."""


class AppInputs:
    """App Inputs"""

    def __init__(self, inputs: 'BaseModel'):
        """Initialize class properties."""
        self.inputs = inputs

    def update_inputs(self):
        """Add custom App models to inputs.

        Input will be validate when the model is added an any exceptions will
        cause the App to exit with a status code of 1.
        """
        self.inputs.add_model(AppBaseModel)
