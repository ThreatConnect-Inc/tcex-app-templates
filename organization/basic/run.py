"""Run App"""
# standard library
import sys
import traceback
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    # third-party
    from tcex import TcEx  # must be imported later, but also needed typing hints

    # first-party
    from app import App  # must be imported later, but also needed typing hints


class Run:
    """Run App"""

    @cached_property
    def app(self) -> 'App':
        """Return a properly configured App instance."""
        # first-party
        from app import App  # pylint: disable=import-outside-toplevel

        return App(self.tcex)

    def exit(self, code: int, msg: str) -> NoReturn:
        """Exit the App."""
        self.tcex.exit.exit(code, msg)  # pylint: disable=no-member

    @cached_property
    def tcex(self) -> 'TcEx':
        """Return a properly configured TcEx instance."""
        # third-party
        from tcex import TcEx  # pylint: disable=import-outside-toplevel

        return TcEx()

    def launch(self):
        """Launch the App"""
        try:
            # perform prep/setup operations
            self.app.setup(**{})

            # run the app
            self.app.run(**{})

            # perform cleanup/teardown operations
            self.app.teardown(**{})

        except Exception as e:
            main_err = f'Generic Error.  See logs for more details ({e}).'
            self.tcex.log.error(traceback.format_exc())
            self.exit(1, main_err)

    def setup(self):
        """Handle the deps directory."""
        # configure the deps directory before importing any third-party packages
        # for TcEx 4 and above, all additional packages are in the "deps" directory
        deps_dir = Path.cwd() / 'deps'
        if not deps_dir.is_dir():
            sys.exit(
                f'Running an App requires a "deps" directory. Could not find the {deps_dir} '
                'directory.\n\nTry running "tcex deps" to install dependencies.'
            )
        sys.path.insert(0, str(deps_dir))  # insert deps directory at the front of the path

    def teardown(self):
        """Teardown the App."""
        # explicitly call the exit method
        self.exit(0, msg=self.app.exit_message)


if __name__ == '__main__':
    # Launch the App
    run = Run()
    run.setup()
    run.launch()
    run.teardown()
