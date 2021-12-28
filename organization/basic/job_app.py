"""App Template."""
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


class JobApp:
    """Job App Class"""

    def __init__(self, _tcex: 'TcEx') -> None:
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
            AppInputs(inputs=self.tcex.inputs).update_inputs()
        except ValidationError as ex:
            self.tcex.exit(code=1, msg=self.inputs.validation_exit_message(ex))

    def run(self) -> None:
        """Run the App main logic."""
        self.log.info('No run logic provided.')

    def setup(self) -> None:
        """Perform setup actions."""
        self.log.trace('feature=app, event=setup')

    def teardown(self) -> None:
        """Perform teardown actions."""
        self.log.trace('feature=app, event=teardown')
