"""ThreatConnect Exchange Playbook App"""

# first-party
from playbook_app import PlaybookApp  # Import default Playbook App Class (Required)


class App(PlaybookApp):
    """ThreatConnect Exchange App"""

    def run(self) -> None:
        """Run the App main logic.

        This method should contain the core logic of the App.
        """

    def write_output(self) -> None:
        """Write the Playbook output variables.

        This method should be overridden with the output variables defined in the install.json
        configuration file.
        """
