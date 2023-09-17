"""App Inputs"""
# pyright: reportGeneralTypeIssues=false

# third-party
from tcex.input.field_type import String
from tcex.input.input import Input
from tcex.input.model.app_trigger_service_model import AppTriggerServiceModel
from tcex.input.model.create_config_model import CreateConfigModel


class ServiceConfigModel(AppTriggerServiceModel):
    """Base model for the App containing any common inputs.

    Trigger Service App inputs do not take playbookDataType.

    This is the configuration input that is sent to the Service
    on startup. The inputs that are configured in the Service
    configuration in the Platform with serviceConfig: true
    """

    # vv: ${TEXT}
    service_input: list[String] | String


class TriggerConfigModel(CreateConfigModel):
    """Base model for Trigger (playbook) config.

    Trigger Playbook inputs do not take playbookDataType.

    This is the configuration input that gets sent to the service
    when a Playbook is enabled (createConfig).
    """

    # pbd: String, vv: ${TEXT}
    trigger_input: String


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
        self.inputs.add_model(ServiceConfigModel)
