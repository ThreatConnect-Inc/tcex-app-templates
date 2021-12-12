"""Service App module for TcEx App."""
# standard library
from typing import TYPE_CHECKING

# third-party
from pydantic import ValidationError

# first-party
from app_inputs import AppInputs

if TYPE_CHECKING:
    # standard library

    # third-party
    from tcex import TcEx
    from tcex.input.input import Input
    from tcex.logger.trace_logger import TraceLogger


class ServiceApp:
    """Service App Class"""

    def __init__(self, _tcex: 'TcEx'):
        """Initialize class properties."""
        self.tcex: 'TcEx' = _tcex

        # properties
        self.exit_message = 'Success'
        self.inputs: 'Input' = self.tcex.inputs
        self.log: 'TraceLogger' = self.tcex.log

        # automatically parse args on init
        self._update_inputs()

    def _update_inputs(self) -> None:
        """Add an custom App models and run validation."""
        try:
            AppInputs(inputs=self.tcex.inputs)
        except ValidationError as ex:
            self.tcex.exit(code=1, msg=ex)

    # pylint: disable=unused-argument
    def create_config_callback(self, trigger_id: str, trigger_input: 'Input', **kwargs) -> dict:
        """Handle create config messages.

        Args:
            trigger_id: The ID of the playbook.
            trigger_input: The playbook config inputs.
            url (str, kwargs): The URL for a webhook trigger.

        Returns:
            dict: A dict containing a **msg** field that can be used to relay error context back to
                playbook and a status boolean. True indicates configuration was successful.
        """
        self.log.trace('create config callback')
        return {'msg': 'Success', 'status': True}

    # pylint: disable=unused-argument
    def delete_config_callback(self, trigger_id: int) -> None:
        """Handle delete config messages.

        Args:
            trigger_id: The ID of the playbook.
        """
        self.log.trace('delete config callback')

    def run(self) -> None:
        """Run the App main logic."""
        self.log.trace('run')

    def setup(self) -> None:
        """Perform setup actions."""
        self.log.trace('feature=app, event=setup')

    def shutdown_callback(self) -> None:
        """Handle shutdown message."""
        self.log.trace('shutdown callback')

    def teardown(self) -> None:
        """Perform teardown actions."""
        self.log.trace('feature=app, event=teardown')
