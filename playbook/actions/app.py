"""ThreatConnect Exchange Playbook App"""
# standard library
from typing import cast

# third-party
from tcex import TcEx
from tcex.app.decorator import OnException, OnSuccess, Output

# first-party
from app_inputs import CapitalizeModel, LowercaseModel, ReverseModel
from playbook_app import PlaybookApp


class App(PlaybookApp):
    """Playbook App"""

    def __init__(self, _tcex: TcEx):
        """Initialize class properties."""
        super().__init__(_tcex)
        self.output_strings = []

    @OnException(exit_msg='Failed to run capitalize action.')
    @OnSuccess(exit_msg='Successfully ran capitalize action.')
    @Output(attribute='output_strings')
    def capitalize(self):
        """Return capitalized string."""
        self.in_ = cast(CapitalizeModel, self.in_)
        return [input_string.capitalize() for input_string in self.in_.input_strings]

    @OnException(exit_msg='Failed to run lowercase action.')
    @OnSuccess(exit_msg='Successfully ran lowercase action.')
    @Output(attribute='output_strings')
    def lowercase(self):
        """Return string in lowercase."""
        self.in_ = cast(LowercaseModel, self.in_)
        return [input_string.lower() for input_string in self.in_.input_strings]

    @OnException(exit_msg='Failed to run reverse action.')
    @OnSuccess(exit_msg='Successfully ran reverse action.')
    @Output(attribute='output_strings')
    def reverse(self):
        """Return string reversed."""
        self.in_ = cast(ReverseModel, self.in_)
        return [input_string[::-1] for input_string in self.in_.input_strings]

    def write_output(self):
        """Write the Playbook output variables."""
        self.log.debug(f'output_strings: {self.output_strings}')

        self.playbook.create.variable('string.action', self.in_.tc_action)
        self.playbook.create.variable('string.outputs', self.output_strings)
        self.playbook.create.variable('string.outputs.count', len(self.output_strings))
