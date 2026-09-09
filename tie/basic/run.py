"""Run App"""

import os
import sys
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

# Add the directory containing this file to sys.path
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

if TYPE_CHECKING:
    from tcex import TcEx  # must be imported later, but also needed typing hints

    from app import App  # must be imported later, but also needed typing hints


class Run:
    """Run App"""

    @cached_property
    def app(self) -> 'App':
        """Return a properly configured App instance."""
        from app import App  # noqa: PLC0415

        return App(self.tcex)

    def exit(self, code: int, msg: str) -> NoReturn:
        """Exit the App."""
        self.tcex.exit.exit(code, msg)

    @cached_property
    def tcex(self) -> 'TcEx':
        """Return a properly configured TcEx instance."""
        from tcex import TcEx  # noqa: PLC0415

        tcex = TcEx()

        return tcex

    def launch(self):
        """Launch the App"""
        try:
            # set app property in testing framework
            # if callable(kwargs.get('set_app')):
            #     kwargs.get('set_app')(self.app)

            # perform prep/setup operations
            self.app.setup()

            # configure the event callback
            self.tcex.app.service.api_event_callback = self.app.api_event_callback  # type: ignore

            # listen on channel/topic
            self.tcex.app.service.listen()

            # start heartbeat threads
            self.tcex.app.service.heartbeat()

            # inform TC that micro-service is Ready
            self.tcex.app.service.ready = True

            # loop until exit
            self.tcex.log.info('feature=app, event=loop-forever')
            if hasattr(self.app, 'loop_forever'):
                self.app.loop_forever()
            else:
                while self.tcex.app.service.loop_forever(sleep=1):
                    pass

            # perform cleanup/teardown operations
            self.app.teardown()

            # explicitly call the exit method
            self.exit(code=0, msg=self.app.exit_message)
        except Exception as e:
            main_err = f'Generic Error.  See logs for more details ({e}).'
            self.tcex.log.exception(main_err)
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
        os.environ['TC_DB_PATH'] = str(self.tcex.inputs.model_unresolved.tc_out_path)

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
