"""Job App"""
# standard library
import os
import traceback

# first-party
from app_lib import AppLib


# pylint: disable=no-member
def run() -> None:
    """Update path and run the App."""

    # update the path to ensure the App has access to required modules
    app_lib = AppLib()
    app_lib.update_path()

    # import modules after path has been updated
    # third-party
    from tcex import TcEx  # pylint: disable=import-outside-toplevel

    # first-party
    from app import App  # pylint: disable=import-outside-toplevel

    config_file = os.environ.get('TCEX_APP_CONFIG_DEV')
    if config_file:
        if not os.path.isfile(config_file):
            raise RuntimeError(f'Missing {config_file} config file.')

    tcex = TcEx(config_file=config_file)

    try:
        # load App class
        app = App(tcex)

        # perform prep/setup operations
        app.setup(**{})

        # run the App logic
        app.run(**{})

        # perform cleanup/teardown operations
        app.teardown(**{})

        # explicitly call the exit method
        tcex.exit(msg=app.exit_message)

    except Exception as ex:
        main_err = f'Generic Error.  See logs for more details ({ex}).'
        tcex.log.error(traceback.format_exc())
        tcex.exit(1, main_err)


if __name__ == '__main__':
    # Run the App
    run()
