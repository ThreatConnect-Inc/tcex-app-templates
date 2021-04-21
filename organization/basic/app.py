"""ThreatConnect Job App"""

# first-party
from job_app import JobApp  # Import default Job App Class (Required)


class App(JobApp):
    """Job App"""

    def run(self) -> None:
        """Run the App main logic.

        This method should contain the core logic of the App.
        """
