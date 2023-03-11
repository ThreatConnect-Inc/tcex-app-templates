"""ThreatConnect Exchange Playbook App"""

# third-party
from tcex import TcEx
from tcex.app.decorator import FailOnOutput, OnException, OnSuccess, Output

# first-party
from playbook_app import PlaybookApp


class App(PlaybookApp):
    """Playbook App"""

    def __init__(self, _tcex: 'TcEx') -> None:
        """Initialize class properties."""
        super().__init__(_tcex)
        self.output_strings = []

    @OnException(exit_msg='Failed to run "append" operation.')
    @OnSuccess(exit_msg='Successfully ran "append" operation.')
    @Output(attribute='output_strings')
    def append(self):
        """Return string with appended character(s)."""
        for input_string in self.inputs.model.input_string:
            return f'{input_string}{self.inputs.model.append_chars}'

    @OnException(exit_msg='Failed to run capitalize action.')
    @OnSuccess(exit_msg='Successfully ran capitalize action.')
    @Output(attribute='output_strings')
    def capitalize(self) -> str:
        """Return capitalized string."""
        for input_string in self.inputs.model.input_string:
            return input_string.capitalize()

    @OnException(exit_msg='Failed to run lowercase action.')
    @OnSuccess(exit_msg='Successfully ran lowercase action.')
    @Output(attribute='output_strings')
    def lowercase(self) -> str:
        """Return string in lowercase."""
        for input_string in self.inputs.model.input_string:
            return input_string.lower()

    @OnException(exit_msg='Failed to run "prepend" operation.')
    @OnSuccess(exit_msg='Successfully ran "prepend" operation.')
    @Output(attribute='output_strings')
    def prepend(self):
        """Return string with prepended character(s)."""
        for input_string in self.inputs.model.input_string:
            return f'{self.inputs.model.prepend_chars}{input_string}'

    @OnException(exit_msg='Failed to run reverse action.')
    @OnSuccess(exit_msg='Successfully ran reverse action.')
    @Output(attribute='output_strings')
    def reverse(self) -> str:
        """Return string reversed."""
        for input_string in self.inputs.model.input_string:
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
        for input_string in self.inputs.model.input_string:
            return str(
                input_string.startswith(
                    self.inputs.model.starts_with_chars,
                    self.inputs.model.starts_with_start,
                    self.inputs.model.starts_with_stop,
                )
            ).lower()

    @OnException(exit_msg='Failed to run strip action.')
    @OnSuccess(exit_msg='Successfully ran strip action.')
    @Output(attribute='output_strings')
    def strip(self) -> str:
        """Return string stripping any whitespaces at beginning and end."""
        for input_string in self.inputs.model.input_string:
            return input_string.strip()

    @OnException(exit_msg='Failed to run swap case action.')
    @OnSuccess(exit_msg='Successfully ran swap case action.')
    @Output(attribute='output_strings')
    def swap_case(self) -> str:
        """Return string with the case swapped."""
        for input_string in self.inputs.model.input_string:
            return input_string.swapcase()

    @OnException(exit_msg='Failed to run title case action.')
    @OnSuccess(exit_msg='Successfully ran title case action.')
    @Output(attribute='output_strings')
    def title_case(self) -> str:
        """Return string in title case."""
        for input_string in self.inputs.model.input_string:
            return input_string.title()

    @OnException(exit_msg='Failed to run uppercase action.')
    @OnSuccess(exit_msg='Successfully ran uppercase action.')
    @Output(attribute='output_strings')
    def uppercase(self) -> str:
        """Return string in uppercase."""
        for input_string in self.inputs.model.input_string:
            return input_string.upper()

    def write_output(self):
        """Write the Playbook output variables."""
        # output
        self.log.debug(f'output_strings: {self.output_strings}')

        self.playbook.create.variable('string.action', self.inputs.model_unresolved.tc_action)
        self.playbook.create.variable('string.outputs', self.output_strings)
        if self.output_strings:
            self.playbook.create.variable('string.outputs.0', self.output_strings[0])
        self.playbook.create.variable('string.outputs.count', len(self.output_strings))
