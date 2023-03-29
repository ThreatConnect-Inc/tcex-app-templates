"""TcEx App Testing Module"""
# standard library
import os
import shutil
import sys
from pathlib import Path

# third-party
from _pytest.config import Config
from _pytest.config.argparsing import Parser
from _pytest.main import Session
from _pytest.python import Metafunc
from tcex_app_testing.util.render.render import Render

# for TcEx 4 and above, all additional packages are in the "deps" directory
deps_dir = Path.cwd() / 'deps'
if not deps_dir.is_dir():
    Render.panel.failure(
        f'Running an App requires a "deps" directory. Could not find the {deps_dir} '
        'directory.\n\nTry running "tcex deps" to install dependencies.'
    )
sys.path.insert(0, str(deps_dir))  # insert deps directory at the front of the path


def clear_log_directory():
    """Clear the App log directory.

    The tests.log file is create before conftest load and therefore would
    delete immediately after being created. This would prevent the log file
    from being viewed, so the log is cleaned up in the __init__.py of tcex-testing.
    """
    log_directory = os.path.join(os.getcwd(), 'log')

    if os.path.isdir(log_directory):
        print('Clearing log directory.')
        for log_file in os.listdir(log_directory):
            file_path = os.path.join(log_directory, log_file)
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)
            if os.path.isfile(file_path) and 'tests.log' not in file_path:
                os.remove(file_path)


def pytest_collection(session: Session):  # pylint: disable=unused-argument
    """Set env var when pytest is in collection mode."""
    os.environ['PYTEST_IN_COLLECTION'] = 'True'


def pytest_collection_finish(session: Session):  # pylint: disable=unused-argument
    """Clean env var when pytest finishes collection mode."""
    if 'PYTEST_IN_COLLECTION' in os.environ:
        del os.environ['PYTEST_IN_COLLECTION']


def profiles(profiles_dir: str) -> list:
    """Get all testing profile names for current feature.

    Args:
        profiles_dir: The profile.d directory for the current test.

    Returns:
        list: All profile names for the current test case.
    """
    profile_names = []
    for filename in sorted(os.listdir(profiles_dir)):
        if filename.endswith('.json'):
            profile_names.append(filename.replace('.json', ''))
    return profile_names


def pytest_addoption(parser: Parser):
    """Add arg flag to control replacement of outputs.

    Args:
        parser: Pytest argparser instance.
    """
    parser.addoption('--merge_inputs', action='store_true')
    parser.addoption('--replace_exit_message', action='store_true')
    parser.addoption('--replace_outputs', action='store_true')
    parser.addoption(
        '--environment',
        action='append',
        help='Sets the TCEX_TEST_ENVS environment variable',
    )


def pytest_generate_tests(metafunc: Metafunc):
    """Generate parametrize values for test_profiles.py::test_profiles tests case.

    Replacing "@pytest.mark.parametrize('profile_name', profile_names)"

    Skip functions that do not accept "profile_name" as an input, specifically this should
    only be used for the test_profiles method in test_profiles.py.
    """
    # we don't add automatic parameterization to anything that doesn't request profile_name
    if 'profile_name' not in metafunc.fixturenames:
        return

    # get the profile.d directory containing JSON profile files
    profile_dir = os.path.join(
        os.path.dirname(os.path.abspath(metafunc.module.__file__)), 'profiles.d'
    )

    profile_names = []
    for profile_name in profiles(profile_dir):
        profile_names.append(profile_name)

    # decorate "test_profiles()" method with parametrize profiles
    metafunc.parametrize('profile_name,', profile_names)


def pytest_unconfigure(config: Config):  # pylint: disable=unused-argument
    """Execute unconfigure logic before test process is exited."""
    log_directory = os.path.join(os.getcwd(), 'log')

    # remove any 0 byte files from log directory
    for root, dirs, files in os.walk(log_directory):  # pylint: disable=unused-variable
        for f in files:
            f = os.path.join(root, f)
            try:
                if os.path.getsize(f) == 0:
                    os.remove(f)
            except OSError:
                continue

    # display any Errors or Warnings in tests.log
    test_log_file = os.path.join(log_directory, 'tests.log')
    if os.path.isfile(test_log_file):
        with open(test_log_file, encoding='utf-8') as fh:
            issues = []
            for line in fh:
                if '- ERROR - ' in line or '- WARNING - ' in line:
                    issues.append(line.strip())

            if issues:
                print('\nErrors and Warnings:')
                for i in issues:
                    print(f'- {i}')

    # remove service started file
    try:
        os.remove('./SERVICE_STARTED')
    except OSError:
        pass


clear_log_directory()
