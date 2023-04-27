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

    def _run_tc_action_method(self):
        # if the data model has the reserved arg of "tc_action", this value is
        # used to trigger a call to the app.<tc_action>() method. an exact match
        # to the method is tried first, followed by a normalization of the tc_action
        # value, and finally an attempt is made to find the reserved "tc_action_map"
        # property to map value to method.
        tc_action: str = self.app.in_.tc_action  # type: ignore
        tc_action_formatted = tc_action.lower().replace(' ', '_')
        tc_action_map = 'tc_action_map'  # reserved property name for action to method map

        # run action method
        if hasattr(self.app, tc_action):
            getattr(self.app, tc_action)()
        elif hasattr(self.app, tc_action_formatted):
            getattr(self.app, tc_action_formatted)()
        elif hasattr(self.app, tc_action_map):
            self.app.tc_action_map.get(tc_action)()  # type: ignore
        else:
            self.exit(1, f'Action method ({tc_action}) was not found.')

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

            # run the App logic
            if (
                hasattr(self.app.in_, 'tc_action')
                and self.app.in_.tc_action is not None  # type: ignore
            ):
                self._run_tc_action_method()
            else:
                # default to run method
                self.app.run(**{})

            # write requested value for downstream Apps
            self.app.write_output()

            # perform cleanup/teardown operations
            self.app.teardown(**{})

        except Exception as e:
            main_err = f'Generic Error.  See logs for more details ({e}).'
            self.tcex.log.error(traceback.format_exc())
            self.exit(1, main_err)

    @staticmethod
    def setup():
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
