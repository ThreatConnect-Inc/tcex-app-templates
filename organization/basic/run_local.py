"""Run App Local"""
# standard library
import json
import os
import sys
from functools import cached_property
from pathlib import Path

# third-party
from dotenv import load_dotenv
from pydantic import BaseSettings, Extra
from tcex import TcEx

# first-party
from run import Run

# load the local .env file
if Path('.env').is_file():
    load_dotenv(dotenv_path=Path('.env'))


class AppInputModel(BaseSettings):
    """Model Definition

    The inputs defined below should all be read from environment
    variables. Either defined globally or in the local .env file.
    Default values are provided when possible.
    """

    # api inputs
    api_default_org: str | None
    tc_api_access_id: str | None
    tc_api_path: str
    tc_api_secret_key: str | None
    tc_token: str | None

    # logging inputs
    tc_log_level: str = 'TRACE'

    # path inputs
    tc_in_path: str = 'log'
    tc_log_path: str = 'log'
    tc_out_path: str = 'log'
    tc_temp_path: str = 'log'

    # proxy inputs
    tc_proxy_host: str | None
    tc_proxy_password: str | None
    tc_proxy_port: int | None
    tc_proxy_tc: bool = False
    tc_proxy_username: str | None

    class Config:
        """DataModel Config"""

        extra = Extra.allow
        case_sensitive = False
        env_file = None
        env_file_encoding = 'utf-8'
        validate_assignment = True


class RunLocal(Run):
    """Run the App locally."""

    _app_inputs: dict = {}

    @property
    def app_inputs(self) -> dict:
        """Return app configuration data."""
        if self._app_inputs is None:
            app_inputs = {}
            app_inputs_json = Path('app_inputs.json')
            if app_inputs_json.is_file():
                with app_inputs_json.open('r', encoding='utf-8') as fh:
                    try:
                        app_inputs = json.load(fh)
                    except ValueError as ex:
                        print(f'Error loading app_inputs.json: {ex}')
                        sys.exit(1)

            self._app_inputs = AppInputModel(**app_inputs).dict()
        return self._app_inputs

    @app_inputs.setter
    def app_inputs(self, config: dict):
        """Set the App Config."""
        self._app_inputs = config

    def exit(self, code: int, msg: str):
        """Exit the App."""
        print('Exit Message:', msg)
        super().exit(code, msg)

    def print_input_data(self):
        """Print the inputs."""
        input_data = json.dumps(self.app_inputs, indent=4, sort_keys=True)
        msg = f'Playbook Input Data:\n' f'{input_data}'
        print(msg)
        self.tcex.log.info(msg)

    @cached_property
    def tcex(self) -> TcEx:
        """Return a properly configured TcEx instance."""
        try:
            # in order to launch locally, configuration data needs to be passed to TcEx
            config_file = os.environ.get('TCEX_APP_CONFIG_DEV')
            if config_file and not os.path.isfile(config_file):
                raise RuntimeError(
                    'The TCEX_APP_CONFIG_DEV environment variable '
                    'is set, but config file could not be found.'
                )

            # the TcEx Input module updates input in order of config, config file, and file params.
            return TcEx(config_file=config_file, config=self.app_inputs)
        except Exception as ex:
            sys.exit(f'Failed to initialize TcEx: {ex}')

    def teardown(self):
        """Teardown the App."""
        self.print_input_data()

        # explicitly call the exit method
        self.exit(0, msg=self.app.exit_message)


if __name__ == '__main__':
    # Launch the App
    run = RunLocal()
    run.setup()
    run.launch()
    run.teardown()
