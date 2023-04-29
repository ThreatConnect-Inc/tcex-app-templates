"""App Inputs"""
# third-party
from tcex.input.input import Input
from tcex.input.model.app_api_service_model import AppApiServiceModel


class AppBaseModel(AppApiServiceModel):
    """Base model for the App containing any common inputs."""


class AppInputs:
    """App Inputs"""

    def __init__(self, inputs: Input):
        """Initialize class properties."""
        self.inputs = inputs

    def update_inputs(self):
        """Add custom App models to inputs.

        Input will be validate when the model is added an any exceptions will
        cause the App to exit with a status code of 1.
        """
        self.inputs.add_model(AppBaseModel)
