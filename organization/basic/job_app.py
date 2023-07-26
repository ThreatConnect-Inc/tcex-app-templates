"""App Template."""
# standard library
from typing import cast

# third-party
from pydantic import ValidationError
from tcex import TcEx

# first-party
from app_inputs import AppBaseModel, AppInputs


class JobApp:
    """Job App Class"""

    def __init__(self, _tcex: TcEx):
        """Initialize class properties."""
        self.tcex: TcEx = _tcex

        # unresolved model must be processed before app_input.py calls add_model(),
        # else validation errors will occur due to the data type not being resolved
        self.in_unresolved = self.tcex.inputs.model_unresolved

        # automatically process inputs on init
        self._update_inputs()

        # properties
        self.exit_message = 'Success'
        self.in_ = cast(AppBaseModel, self.tcex.inputs.model)
        self.log = self.tcex.log

    def _update_inputs(self):
        """Add an custom App models and run validation."""
        try:
            AppInputs(inputs=self.tcex.inputs).update_inputs()
        except ValidationError as ex:
            self.tcex.exit.exit(code=1, msg=self.tcex.inputs.validation_exit_message(ex))

    def run(self):
        """Run the App main logic."""
        self.log.info('No run logic provided.')

    def setup(self):
        """Perform setup actions."""
        self.log.trace('feature=app, event=setup')

    def teardown(self):
        """Perform teardown actions."""
        self.log.trace('feature=app, event=teardown')
