"""Playbook App Template."""
# third-party
from tcex import TcEx

# first-party
from app_inputs import App_Inputs


class PlaybookApp:
    """Playbook App Class."""

    def __init__(self, _tcex: TcEx) -> None:
        """Initialize class properties."""
        self.tcex: TcEx = _tcex

        # properties
        self.exit_message = 'Success'
        self.inputs = self.tcex.inputs
        self.log = self.tcex.log

        # automatically parse args on init
        self._update_inputs()

    def _update_inputs(self) -> None:
        """Add an custom App models and run validation."""
        App_Inputs(inputs=self.tcex.inputs)

    def run(self) -> None:
        """Run the App main logic."""
        self.log.info('No run logic provided.')

    def setup(self) -> None:
        """Perform prep/setup logic."""
        self.log.trace('setup')

    def teardown(self) -> None:
        """Perform cleanup/teardown logic."""
        self.log.trace('teardown')

    def write_output(self) -> None:
        """Write the Playbook output variables."""
        self.log.info('No output variables written.')
