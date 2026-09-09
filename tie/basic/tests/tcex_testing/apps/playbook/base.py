"""Playbook test case — test classes inherit directly from this.

Test classes inherit from PlaybookTestCase (or from each other). The
class IS the harness — no fixture parameters needed anywhere.

    APP_DIR = Path(__file__).parent.parent

    class TestHash(PlaybookTestCase):
        app_dir = APP_DIR

        def test_single(self):
            result = self.run(Profile(
                inputs={'tc_action': 'Hash', 'input_binary': b'hello world'},
                expected=PlaybookExpected(
                    exit_codes=[0],
                    outputs={
                        'outputs.binary.action': 'Hash',
                        'outputs.binary.md5.0': Check.is_string(),
                    },
                ),
            ))

TC staging is handled via Profile.stage — class-level TC objects go in stage():

    class TestEnrichIndicator(PlaybookTestCase):
        app_dir = APP_DIR

        def stage(self) -> None:
            self.stager.stage('target', 'indicators/addresses', {'summary': '1.2.3.4'})

        def test_enrich(self):
            result = self.run(Profile(
                inputs={
                    'tc_action': 'Enrich Indicator',
                    'indicator_id': self.staged['target']['data']['id'],
                },
                expected=PlaybookExpected(exit_codes=[0]),
            ))

Apps that call a vendor SDK can opt into mock/live mode:

    class TestVirusTotalLookup(PlaybookTestCase):
        app_dir = APP_DIR
        use_mock = True

        def create_mock_sdk(self):
            return MockVirusTotalSDK()

        def create_sdk(self):
            return VirusTotalSDK(api_key=self.resolve('${env:VT_API_KEY}'))

        def test_known_malicious(self):
            result = self.run(Profile(
                inputs={'tc_action': 'Lookup Hash', 'file_hash': 'abc123...'},
                expected=PlaybookExpected(
                    exit_codes=[0],
                    outputs={'outputs.is_malicious': 'true'},
                ),
            ))

Apps with no SDK (pure transforms) ignore use_mock / create_*_sdk entirely.
"""

from __future__ import annotations

# standard library
import os
from unittest.mock import patch

# third-party
import pytest

# third-party
from tcex_testing.apps.playbook.profile import Profile
from tcex_testing.apps.playbook.result import AppResult
from tcex_testing.apps.playbook.runner import AppRunner
from tcex_testing.harness import TestCaseBase


class PlaybookTestCase(TestCaseBase):
    """Base for playbook test classes. Inherit this directly in test files.

    No configuration needed — app_dir is resolved automatically from the
    location of the concrete test class file (assumes tests live in tests/).
    use_mock controls whether create_mock_sdk() or create_sdk() is called.
    Apps with no SDK leave both methods returning None — run() skips patching.
    """

    # -- pytest per-test lifecycle --------------------------------------------

    def setup_method(self, method=None):
        super().setup_method(method)

    def teardown_method(self, *_):
        self.teardown()
        super().teardown_method()

    # -- Optional SDK override (for apps that call a vendor SDK) --------------

    def create_sdk(self):
        """Return a live vendor SDK instance.

        Override if the app uses a vendor SDK and you need live tests.
        Return None (default) for pure transform apps with no external calls.
        """
        return None

    def create_mock_sdk(self):
        """Return a fixture-backed mock SDK instance.

        Override if the app uses a vendor SDK and you need mock tests.
        Return None (default) for pure transform apps with no external calls.
        """
        return None

    # -- Test interface -------------------------------------------------------

    def run(self, profile: Profile) -> AppResult:
        """Run the app with the given profile; assert expected results; return AppResult.

        SDK selection:
          use_mock=True → create_mock_sdk(); loads from fixture files
          use_mock=False → create_sdk(); hits real vendor API
          both return None → no patching; pure transform app

        Per-test TC staging from profile.stage.threatconnect is handled here.
        Class-level TC staging is handled by the stage() override.
        """
        if profile.environments:
            active = set(os.environ.get('TCEX_TEST_ENVS', '').split(','))
            if not (set(profile.environments) & active):
                pytest.skip(f'environments {profile.environments!r} not in TCEX_TEST_ENVS={active!r}')

        for item in profile.stage.threatconnect:
            try:
                self.stager.stage(key=item.key, path=item.path, body=item.body, params=item.params)
            except Exception:
                self.stager.cleanup()
                raise

        resolved_inputs = self.resolver.resolve(dict(profile.inputs))

        if self.use_mock:
            sdk = self.create_mock_sdk()
            if sdk is not None:
                sdk._load_fixtures(self.fixture_paths)
        else:
            sdk = self.create_sdk()

        runner = AppRunner(self.app_dir, self._output_dir)

        profile.before(self)

        with patch.dict(os.environ, profile.stage.env):
            result = runner.run(resolved_inputs, sdk=sdk)

        resolved = profile.fetch_records(result)
        profile.assert_result(result, resolved)
        profile.after(self, result)

        return result
