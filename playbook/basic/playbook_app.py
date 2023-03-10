"""Playbook App Template."""

# third-party
from pydantic import ValidationError
from tcex import TcEx
from tcex.app.playbook.playbook import Playbook
from tcex.input.input import Input
from tcex.logger.trace_logger import TraceLogger

# first-party
from app_inputs import AppBaseModel, AppInputs


class PlaybookApp:
    """Playbook App Class."""

    def __init__(self, _tcex: TcEx):
        """Initialize class properties."""
        self.tcex: TcEx = _tcex

        # properties
        self.exit_message = 'Success'
        self.inputs: Input = self.tcex.inputs
        self.model: AppBaseModel = self.inputs.model  # type: ignore
        self.log: TraceLogger = self.tcex.log
        self.playbook: Playbook = self.tcex.app.playbook

        # automatically parse args on init
        self._update_inputs()

    def _update_inputs(self):
        """Add an custom App models and run validation."""
        try:
            AppInputs(inputs=self.tcex.inputs).update_inputs()
        except ValidationError as ex:
            self.tcex.exit.exit(code=1, msg=self.inputs.validation_exit_message(ex))

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
