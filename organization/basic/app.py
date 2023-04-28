"""ThreatConnect Exchange Job App."""

# first-party
from job_app import JobApp


class App(JobApp):
    """ThreatConnect Exchange App."""

    def run(self) -> None:
        """Run the App main logic.

        This method should contain the core logic of the App.
        """
        self.log.info(f'Sample Input is: {self.in_.dict()}')
