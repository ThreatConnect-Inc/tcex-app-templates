"""App Inputs"""
# pyright: reportGeneralTypeIssues=false

# third-party
from tcex.input.input import Input
from tcex.input.model.app_api_service_model import AppApiServiceModel


class AppBaseModel(AppApiServiceModel):
    """Base model for the App containing any common inputs."""


class AppInputs:
    """App Inputs"""

    def __init__(self, inputs: Input):
        """Initialize instance properties."""
        self.inputs = inputs

    def update_inputs(self):
        """Add custom App model to inputs.

        Input will be validate when the model is added an any exceptions will
        cause the App to exit with a status code of 1.
        """
        self.inputs.add_model(AppBaseModel)
