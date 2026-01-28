"""App Module"""

# standard library
# standard library
from abc import ABC

# third-party
from pydantic import ValidationError
from tcex import TcEx
from tcex.exit import ExitCode
from tcex.input.input import Input
from tcex.logger.trace_logger import TraceLogger

# first-party
# TODO: make AppInputs abstract and import here
from app_inputs import AppInputs


class ApiServiceAppABC(ABC):  # noqa: B024
    """Service App Class"""

    def __init__(self, _tcex: TcEx):
        """Initialize class properties."""
        self.tcex: TcEx = _tcex

        # properties
        self.exit_message = 'Success'
        self.inputs: Input = self.tcex.inputs

        self.log: TraceLogger = self.tcex.log

        self.log.warning('event=app-init, message=App Initiated')

        # automatically parse args on init
        self._update_inputs()

    def _update_inputs(self) -> None:
        """Add an custom App models and run validation."""
        try:
            AppInputs(inputs=self.tcex.inputs).update_inputs()
        except ValidationError as ex:
            self.tcex.exit.exit(code=ExitCode.FAILURE, msg=str(ex))

    def setup(self) -> None:
        """Perform setup actions."""
        self.log.trace('feature=app, event=setup')

    def shutdown_callback(self) -> None:
        """Handle the shutdown message."""
        self.log.trace('feature=app, event=shutdown-callback')

    def teardown(self) -> None:
        """Perform teardown actions."""
        self.log.trace('feature=app, event=teardown')
