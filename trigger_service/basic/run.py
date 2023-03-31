"""Playbook App"""
# standard library
import traceback

# first-party
from app_lib import AppLib


def run(**kwargs) -> None:
    """Update path and run the App."""

    # update the path to ensure the App has access to required modules
    app_lib = AppLib()
    app_lib.update_path()

    # import modules after path has been updated

    # third-party
    from tcex import TcEx  # pylint: disable=import-outside-toplevel

    # first-party
    from app import App  # pylint: disable=import-outside-toplevel

    tcex = TcEx()

    try:
        # load App class
        app = App(tcex)

        # set app property in testing framework
        if callable(kwargs.get('set_app')):
            kwargs.get('set_app')(app)

        # configure custom trigger message handler
        # pylint: disable=no-member
        tcex.app.service.create_config_callback = app.create_config_callback
        tcex.app.service.delete_config_callback = app.delete_config_callback
        tcex.app.service.shutdown_callback = app.shutdown_callback

        # first-party
        from app_inputs import TriggerConfigModel  # pylint: disable=no-name-in-module

        # set the createConfig model
        tcex.app.service.trigger_input_model = TriggerConfigModel

        # perform prep/setup operations
        app.setup(**{})

        # listen on channel/topic
        tcex.app.service.listen()

        # start heartbeat threads
        tcex.app.service.heartbeat()

        # inform TC that micro-service is Ready
        tcex.app.service.ready = True

        # run app logic
        app.run()

        # perform cleanup/teardown operations
        app.teardown()

        # explicitly call the exit method
        tcex.exit.exit(msg=app.exit_message)

    except Exception as e:
        main_err = f'Generic Error.  See logs for more details ({e}).'
        tcex.log.error(traceback.format_exc())
        tcex.exit.exit(1, main_err)


if __name__ == '__main__':
    # Run the App
    run()
