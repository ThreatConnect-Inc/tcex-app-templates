"""ThreatConnect Playbook App"""
# standard library
import json

# third-party
from tcex import TcEx

# first-party
from playbook_app import PlaybookApp  # Import default Playbook App Class (Required)


class App(PlaybookApp):
    """Playbook App"""

    def __init__(self, _tcex: TcEx):
        """Initialize class properties.

        This method can be OPTIONALLY overridden.
        """
        super().__init__(_tcex)
        self.pretty_json = {}

    def run(self):
        """Run the App main logic.

        This method should contain the core logic of the App.
        """
        # read inputs

        # get the playbook variable type
        json_data_type: str = self.playbook.get_variable_type(self.in_unresolved.json_data)

        # convert string input to dict
        try:
            if json_data_type in ['String']:
                json_data: dict = json.loads(self.in_.json_data)
        except ValueError:
            self.tcex.exit(1, 'Failed parsing JSON data.')

        # generate the new "pretty" json (this will be used as an option variable)
        try:
            self.pretty_json: str = json.dumps(
                json_data, indent=self.in_.indent, sort_keys=self.in_.sort_keys
            )
        except ValueError:
            self.tcex.exit(1, 'Failed parsing JSON data.')

        # set the App exit message
        self.exit_message = 'JSON prettified.'  # pylint: disable=attribute-defined-outside-init

    def write_output(self):
        """Write the Playbook output variables.

        This method should be overridden with the output variables defined in the install.json
        configuration file.
        """
        self.log.info('Writing Output')
        self.playbook.create.string('json.pretty', self.pretty_json)
