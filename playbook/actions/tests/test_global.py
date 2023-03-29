"""TcEx App Testing Module"""

# third-party
from tcex_app_testing import __metadata__


def test_framework_version():
    """Verify that the testing framework version installed matches what is expected."""
    installed_version = __metadata__.__version__
    with open('requirements_dev.txt', encoding='utf-8') as req_dev:
        req = [
            r
            for r in req_dev.readlines()
            if 'tcex-app-testing' in r and not r.strip().startswith('#')
        ]
        assert installed_version in req[0]
