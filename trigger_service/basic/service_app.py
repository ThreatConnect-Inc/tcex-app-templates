"""Service App module for TcEx App."""
# standard library
from typing import cast

# third-party
from pydantic import ValidationError
from tcex import TcEx

# first-party
from app_inputs import AppInputs, ServiceConfigModel, TriggerConfigModel


class ServiceApp:
    """Service App Class"""

    def __init__(self, _tcex: TcEx):
        """Initialize class properties."""
        self.tcex: TcEx = _tcex

        # unresolved model must be processed before app_input.py calls add_model(),
        # else validation errors will occur due to the data type not being resolved
        self.in_unresolved = self.tcex.inputs.model_unresolved

        # automatically parse args on init
        self._update_inputs()

        # properties
        self.exit_message = 'Success'
        self.in_ = cast(ServiceConfigModel, self.tcex.inputs.model)
        self.log = self.tcex.log

    def _update_inputs(self):
        """Add an custom App models and run validation."""
        try:
            AppInputs(inputs=self.tcex.inputs).update_inputs()
        except ValidationError as ex:
            self.tcex.exit.exit(code=1, msg=self.tcex.inputs.validation_exit_message(ex))

    # pylint: disable=unused-argument
    def create_config_callback(self, trigger_input: TriggerConfigModel, **kwargs) -> dict:
        """Handle create config messages.

        Args:
            trigger_id: The ID of the playbook.
            trigger_input: The playbook config inputs.
            url (str, kwargs): The URL for a webhook trigger.

        Returns:
            dict: A dict containing a **msg** field that can be used to relay error context back to
                playbook and a status boolean. True indicates configuration was successful.
        """
        self.log.trace(f'create config callback for {trigger_input}')
        return {'msg': 'Success', 'status': True}

    # pylint: disable=unused-argument
    def delete_config_callback(self, trigger_id: int):
        """Handle delete config messages.

        Args:
            trigger_id: The ID of the playbook.
        """
        self.log.trace('delete config callback')

    def run(self):
        """Run the App main logic."""
        self.log.trace('run')

    def setup(self):
        """Perform setup actions."""
        self.log.trace('feature=app, event=setup')

    def shutdown_callback(self):
        """Handle shutdown message."""
        self.log.trace('shutdown callback')

    def teardown(self):
        """Perform teardown actions."""
        self.log.trace('feature=app, event=teardown')
