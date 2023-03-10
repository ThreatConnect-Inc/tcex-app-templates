"""Run App Local"""
# standard library
import json
import os
from functools import cached_property
from typing import TYPE_CHECKING, cast

# third-party
from tcex.app.key_value_store.key_value_redis import KeyValueRedis

# first-party
from run import Run

if TYPE_CHECKING:
    # third-party
    from tcex import TcEx


class RunLocal(Run):
    """Run the App locally."""

    context = '7979'

    @cached_property
    def client(self):
        """Return an instance of KeyValueRedis"""
        return cast(KeyValueRedis, self.tcex.app.key_value_store.client)

    @cached_property
    def tcex(self) -> 'TcEx':
        """Return a properly configured TcEx instance."""
        # third-party
        from tcex import TcEx  # pylint: disable=import-outside-toplevel
        from tcex.app.config.install_json import InstallJson

        # in order to launch locally, configuration data needs to be passed to TcEx
        config = {}
        config_file = os.environ.get('TCEX_APP_CONFIG_DEV')
        if config_file:
            if not os.path.isfile(config_file):
                raise RuntimeError(f'Missing {config_file} config file.')

            config = {
                'tc_playbook_db_type': 'Mock',
                'tc_playbook_db_context': self.context,
                'tc_playbook_out_variables': InstallJson().tc_playbook_out_variables,
            }

        return TcEx(config_file=config_file, config=config)

    def launch(self):
        """Launch the App"""
        exit_msg = super().launch()

        msg = (
            f'Output variables written:\n'
            f'{json.dumps(self.client.get_all(self.context), indent=2)}'
        )
        print(msg)
        self.tcex.log.info(msg)

        return exit_msg


if __name__ == '__main__':
    # Launch the App
    run = Run()
    exit_msg = run.launch()
    run.exit(0, msg=exit_msg)
