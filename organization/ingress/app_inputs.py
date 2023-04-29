"""App Inputs"""
# third-party
from tcex.input.field_type import String
from tcex.input.input import Input
from tcex.input.model.app_organization_model import AppOrganizationModel


class AppBaseModel(AppOrganizationModel):
    """Base model for the App containing any common inputs."""

    tc_owner: String


class AppInputs:
    """App Inputs"""

    def __init__(self, inputs: Input):
        """Initialize class properties."""
        self.inputs = inputs

    def update_inputs(self):
        """Add custom App models to inputs. Validation will run at the same time."""
        self.inputs.add_model(AppBaseModel)
