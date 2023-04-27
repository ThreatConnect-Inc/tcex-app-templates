"""ThreatConnect Exchange Playbook App"""
# standard library
from typing import cast

# third-party
from tcex import TcEx
from tcex.app.decorator import FailOnOutput, OnException, OnSuccess, Output

# first-party
from app_inputs import (
    AppendModel,
    CapitalizeModel,
    LowerCaseModel,
    PrependModel,
    ReverseModel,
    StartsWithModel,
)
from playbook_app import PlaybookApp


class App(PlaybookApp):
    """Playbook App"""

    def __init__(self, _tcex: TcEx):
        """Initialize class properties."""
        super().__init__(_tcex)
        self.output_strings = []

    @OnException(exit_msg='Failed to run "append" operation.')
    @OnSuccess(exit_msg='Successfully ran "append" operation.')
    @Output(attribute='output_strings')
    def append(self):
        """Return string with appended character(s)."""
        self.in_ = cast(AppendModel, self.in_)
        for input_string in self.in_.input_strings:
            return f'{input_string}{self.in_.append_chars}'

    @OnException(exit_msg='Failed to run capitalize action.')
    @OnSuccess(exit_msg='Successfully ran capitalize action.')
    @Output(attribute='output_strings')
    def capitalize(self):
        """Return capitalized string."""
        self.in_ = cast(CapitalizeModel, self.in_)
        for input_string in self.in_.input_strings:
            return input_string.capitalize()

    @OnException(exit_msg='Failed to run lowercase action.')
    @OnSuccess(exit_msg='Successfully ran lowercase action.')
    @Output(attribute='output_strings')
    def lowercase(self):
        """Return string in lowercase."""
        self.in_ = cast(LowerCaseModel, self.in_)
        for input_string in self.in_.input_strings:
            return input_string.lower()

    @OnException(exit_msg='Failed to run "prepend" operation.')
    @OnSuccess(exit_msg='Successfully ran "prepend" operation.')
    @Output(attribute='output_strings')
    def prepend(self):
        """Return string with prepended character(s)."""
        self.in_ = cast(PrependModel, self.in_)
        for input_string in self.in_.input_strings:
            return f'{self.in_.prepend_chars}{input_string}'

    @OnException(exit_msg='Failed to run reverse action.')
    @OnSuccess(exit_msg='Successfully ran reverse action.')
    @Output(attribute='output_strings')
    def reverse(self):
        """Return string reversed."""
        self.in_ = cast(ReverseModel, self.in_)
        for input_string in self.in_.input_strings:
            return input_string[::-1]

    @OnException(exit_msg='Failed to run "starts with" operation.')
    @FailOnOutput(
        fail_enabled='fail_on_false',
        fail_on=['false'],
        fail_msg='Operation "starts with" returned "false".',
    )
    @OnSuccess(exit_msg='Successfully ran "starts with" operation.')
    @Output(attribute='output_strings')
    def starts_with(self):
        """Return true if string starts with provided characters."""
        self.in_ = cast(StartsWithModel, self.in_)
        for input_string in self.in_.input_strings:
            return str(
                input_string.startswith(
                    self.in_.starts_with_chars,
                    self.in_.starts_with_start,
                    self.in_.starts_with_stop,
                )
            ).lower()

    def write_output(self):
        """Write the Playbook output variables."""
        self.log.debug(f'output_strings: {self.output_strings}')

        self.playbook.create.variable('string.action', self.in_unresolved.tc_action)
        self.playbook.create.variable('string.outputs', self.output_strings)
        self.playbook.create.variable('string.outputs.count', len(self.output_strings))
