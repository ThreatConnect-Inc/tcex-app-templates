"""Run to test TIE application."""

# standard library
import json
import os
import shutil
import subprocess
from pathlib import Path

# third-party
from tcex_app_testing.env_store import EnvStore


@staticmethod
def _should_we_run():
    """Check environment variables to see if we should run."""
    test_envs = os.environ.get('TCEX_TEST_ENVS', None)

    # force to local only as these tests are only for local testing
    if test_envs and 'local' in test_envs:
        return True

    return False


@staticmethod
def _run_test(test_file: str):
    """Run the servers."""
    # pylint: disable=consider-using-with
    p1 = subprocess.Popen(f'tcex run --config-json {test_file}', shell=True)
    p1.wait()


def test_run_local():
    """."""
    # set to local only as sometimes the website is not available
    if _should_we_run():
        env_store = EnvStore()

        temp_file_contents = {
            'stage': {},
            'inputs': {
                'bearer_token': env_store.getenv('/ninja/int/flashpoint/ignite_api_key'),
                'filter_include_tags': '',
                'filter_exclude_tags': '',
                'flashpoint_types': ['Event', 'FP Attribute', 'Report', 'Vulnerability'],
                'tc_api_path': os.environ.get('TC_API_PATH', None),
                'tc_api_access_id': os.environ.get('TC_API_ACCESS_ID', None),
                'tc_api_secret_key': os.environ.get('TC_API_SECRET_KEY', None),
                'tc_log_level': 'debug',
                'tc_owner': 'Flashpoint Intelligence Local',
                'tc_proxy_external': 'false',
                'tc_proxy_host': 'localhost',
                'tc_proxy_password': '',
                'tc_proxy_port': '3128',
                'tc_proxy_username': '',
            },
        }

        # remove log folder
        shutil.rmtree('log', ignore_errors=True)

        # write to a tmp file
        with Path.open('tests/local-temp-run.json', 'w', encoding='UTF-8') as f:
            f.write(json.dumps(temp_file_contents))

        # run the test, using the tmp file
        _run_test('tests/local-temp-run.json')

    assert True
