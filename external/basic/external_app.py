"""External App Template"""

# third-party
from typing import cast
from pydantic import ValidationError
from tcex import TcEx

# first-party
from app_inputs import AppBaseModel, AppInputs


class ExternalApp:
    """Get the owners and indicators in the given owner."""

    def __init__(self, _tcex: TcEx):
        """Initialize class properties."""
        self.tcex = _tcex

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
        """Perform run actions."""
        self.log.info('No run logic provided.')

    def setup(self):
        """Perform setup actions."""
        self.log.trace('feature=app, event=setup')

    def teardown(self):
        """Perform teardown actions."""
        self.log.trace('feature=app, event=teardown')
