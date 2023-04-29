"""App Inputs"""
# third-party
from pydantic import BaseModel
from tcex.input.field_type import Choice, sensitive, string


class AppBaseModel(BaseModel):
    """Base model for the App containing any common inputs."""

    external_tc_url: string(allow_empty=False, strip=True)
    external_tc_api_access_id: string(allow_empty=False, strip=True)
    external_tc_api_secret_key: sensitive(allow_empty=False)
    external_tc_owner: string(allow_empty=False, strip=True)
    tql: string(allow_empty=False, strip=True)
    tc_owner: Choice


class AppInputs:
    """App Inputs"""

    def __init__(self, inputs: 'BaseModel'):
        """Initialize class properties."""
        self.inputs = inputs

    def update_inputs(self):
        """Add custom App models to inputs.

        Input will be validated when the model is added an any exceptions will
        cause the App to exit with a status code of 1.
        """
        self.inputs.add_model(AppBaseModel)
