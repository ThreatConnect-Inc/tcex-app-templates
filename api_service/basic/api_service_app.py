"""App Module"""
# standard library
from typing import cast

# third-party
from pydantic import ValidationError
from tcex import TcEx

# first-party
from app_inputs import AppBaseModel, AppInputs


class ApiServiceApp:
    """Service App Class"""

    def __init__(self, _tcex: TcEx):
        """Initialize class properties."""
        self.tcex: TcEx = _tcex

        # automatically process inputs on init
        self._update_inputs()

        # properties
        self.exit_message = 'Success'
        self.in_ = cast(AppBaseModel, self.tcex.inputs.model)
        self.in_unresolved = cast(AppBaseModel, self.tcex.inputs.model_unresolved)
        self.log = self.tcex.log

    def _update_inputs(self):
        """Add an custom App models and run validation."""
        try:
            AppInputs(inputs=self.tcex.inputs).update_inputs()
        except ValidationError as ex:
            self.tcex.exit.exit(code=1, msg=self.tcex.inputs.validation_exit_message(ex))

    def setup(self):
        """Perform setup actions."""
        self.log.trace('feature=app, event=setup')

    def shutdown_callback(self):
        """Handle the shutdown message."""
        self.log.trace('feature=app, event=shutdown-callback')

    def teardown(self):
        """Perform teardown actions."""
        self.log.trace('feature=app, event=teardown')
