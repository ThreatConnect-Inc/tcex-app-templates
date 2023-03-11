"""Run App Local"""
# standard library
import json
import os
import sys
from functools import cached_property
from typing import cast

# third-party
from tcex import TcEx
from tcex.app.config.install_json import InstallJson
from tcex.app.key_value_store.key_value_redis import KeyValueRedis

# first-party
from run import Run


class RunLocal(Run):
    """Run the App locally."""

    context = '7979'

    @cached_property
    def client(self):
        """Return an instance of KeyValueRedis"""
        return cast(KeyValueRedis, self.tcex.app.key_value_store.client)

    @cached_property
    def app_config(self) -> dict:
        """Return app configuration data."""
        app_config = {
            'api_default_org': os.getenv('API_DEFAULT_ORG'),
            'tc_api_access_id': os.getenv('TC_API_ACCESS_ID'),
            'tc_api_path': os.getenv('TC_API_PATH'),
            'tc_api_secret_key': os.getenv('TC_API_SECRET_KEY'),
            'tc_token': os.getenv('TC_TOKEN'),
            'tc_log_level': os.getenv('TC_LOG_LEVEL', 'TRACE'),
            'tc_log_path': os.getenv('TC_LOG_PATH', 'app.log'),
            'tc_proxy_host': os.getenv('TC_PROXY_HOST'),
            'tc_proxy_password': os.getenv('TC_PROXY_PASSWORD'),
            'tc_proxy_port': os.getenv('TC_PROXY_PORT'),
            'tc_proxy_tc': False,
            'tc_proxy_username': os.getenv('TC_PROXY_USERNAME'),
        }
        # path config
        app_config.update(
            {
                'tc_in_path': os.getenv('TC_IN_PATH', 'log'),
                'tc_log_path': os.getenv('TC_IN_PATH', 'log'),
                'tc_out_path': os.getenv('TC_IN_PATH', 'log'),
                'tc_temp_path': os.getenv('TC_IN_PATH', 'log'),
            }
        )
        # specifically for playbook Apps
        app_config.update(
            {
                'tc_playbook_kvstore_context': self.context,
                # 'tc_kvstore_host': os.getenv('TC_KVSTORE_HOST', 'localhost'),
                # 'tc_kvstore_port': os.getenv('TC_KVSTORE_PORT', '6379'),
                'tc_kvstore_type': os.getenv('TC_KVSTORE_TYPE', 'Mock'),
                'tc_playbook_out_variables': InstallJson().tc_playbook_out_variables,
            }
        )
        return app_config

    def log_output_data(self):
        """Log the playbook output data."""

        output_data = self.client.get_all(self.context)
        if output_data:
            msg = (
                f'Output variables written:\n'
                f'{json.dumps(self.client.get_all(self.context), indent=2)}'
            )
            print(msg)
            self.tcex.log.info(msg)

    @cached_property
    def tcex(self) -> 'TcEx':
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
            return TcEx(config_file=config_file, config=self.app_config)
        except Exception as ex:
            sys.exit(f'Failed to initialize TcEx: {ex}')

    def launch(self):
        """Launch the App"""
        exit_msg_ = super().launch()

        # log outputs
        self.log_output_data()

        return exit_msg_


if __name__ == '__main__':
    # Launch the App
    run = RunLocal()
    exit_msg = run.launch()
    print(exit_msg)
    run.exit(0, msg=exit_msg)
