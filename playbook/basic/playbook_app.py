"""Playbook App Template."""

# standard library
from typing import cast

# third-party
from pydantic import ValidationError
from tcex import TcEx

# first-party
from app_inputs import AppBaseModel, AppInputs


class PlaybookApp:
    """Playbook App Class."""

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
        self.playbook = self.tcex.app.playbook
        self.out = self.tcex.app.playbook.create

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
        """Perform prep/setup logic."""
        self.log.trace('setup')

    def teardown(self):
        """Perform cleanup/teardown logic."""
        self.log.trace('teardown')

    def write_output(self):
        """Write the Playbook output variables."""
        self.log.info('No output variables written.')
