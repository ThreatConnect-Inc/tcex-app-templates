"""Job (Organization) app test case base class.

Test classes inherit from a per-app AppTestCase (which inherits JobTestCase).
create_sdk and create_mock_sdk are defined once on AppTestCase, not repeated
in every test file.

Two run modes (set as class vars):
  use_mock=True    Fixture SDK + upload stubbed → assert batch files on disk
  use_mock=False   Real SDK + real upload       → assert TC platform state

Usage:
    # tests/harness/base.py
    class AppTestCase(JobTestCase):
        use_mock = True
        def create_sdk(self): ...
        def create_mock_sdk(self): ...

    # tests/test_events.py
    class TestEvents(AppTestCase):
        def test_run(self):
            result = self.run(Profile(inputs={'hours_back': 24}))
            result.assert_no_batch_errors()
"""
from __future__ import annotations

# standard library
import os
from abc import abstractmethod
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

# third-party
import pytest
from tcex.api.tc.util.threat_intel_util import ThreatIntelUtil
from tcex.input.field_type.edit_choice import EditChoice

from tcex.input.field_type.exception import InvalidEmptyValue
from tcex_testing.apps.job.profile import Profile
from tcex_testing.apps.job.result import JobResult
from tcex_testing.harness import TestCaseBase


class JobTestCase(TestCaseBase):
    """Base class for Organization/Job app tests.

    Subclass this once per app as AppTestCase (in tests/harness/base.py) and
    define create_sdk / create_mock_sdk there. Individual test files inherit
    from AppTestCase — not from JobTestCase directly.

    app_dir is resolved automatically from the concrete class file location.
    """

    sdk: Any = None

    # When set, patch this dotted path with the mock SDK instead of calling
    # _inject_sdk. Use this when app.py does `from sdk.sdk import SDK` and
    # constructs the SDK locally — setting app.sdk has no effect in that case.
    #
    #     patch_sdk_module_path = 'app.SDK'
    patch_sdk_module_path: str | None = None

    # -- pytest per-test lifecycle --------------------------------------------

    def setup_method(self, method=None) -> None:
        self.sdk = None
        super().setup_method(method)

    def teardown_method(self, *_) -> None:
        self.teardown()
        super().teardown_method()

    def teardown(self) -> None:
        """No-op by default. Override for app-specific cleanup."""

    # -- Abstract interface ----------------------------------------------------

    @abstractmethod
    def create_sdk(self):
        """Return a real vendor SDK instance using live credentials."""

    @abstractmethod
    def create_mock_sdk(self):
        """Return a fixture-backed mock SDK instance."""

    # -- App runner ------------------------------------------------------------

    def run(self, profile: Profile) -> JobResult:
        """Run the app with the given profile; assert expected results; return JobResult.

        Returns a JobResult for chaining assertions:

            result = self.run(Profile(inputs={'hours_back': 24}))
            result.assert_no_batch_errors()
        """
        if profile.environments:
            active = set(os.environ.get('TCEX_TEST_ENVS', '').split(','))
            if not (set(profile.environments) & active):
                pytest.skip(f'environments {profile.environments!r} not in TCEX_TEST_ENVS={active!r}')

        from app import App  # noqa: PLC0415

        inputs = self.resolver.resolve(dict(profile.inputs))
        self._setup_tcex(inputs)
        self._setup_logging()

        assert self.tcex is not None, 'tcex not initialized — setup_method must run before run()'
        # App.__init__ calls _update_inputs() which applies AppBaseModel validation (including
        # Sensitive wrapping, AdvancedSettingsModel parsing, Choice field resolution).
        # Create App FIRST so tcex.inputs.model is the fully-validated AppBaseModel before
        # create_mock_sdk/create_sdk read it.
        # In mock mode, bypass Choice TC API calls during App.__init__.
        if self.use_mock:
            with self._choice_validation_bypass():
                app = App(self.tcex)
            self.sdk = self.create_mock_sdk()
            if self.sdk is not None:
                self.sdk._load_fixtures(self.fixture_paths)
        else:
            app = App(self.tcex)
            self.sdk = self.create_sdk()

        # Inject SDK — use attribute injection by default; use module-level patch
        # when patch_sdk_module_path is set (for apps that import SDK locally).
        if self.sdk is not None and not self.patch_sdk_module_path:
            self._inject_sdk(app, self.sdk)

        profile.before(self)

        self._call_app_run(app, profile)

        exit_code = int(self.tcex.exit.code)
        msg_path = self._output_dir / 'message.tc'
        exit_message = msg_path.read_text(encoding='utf-8') if msg_path.is_file() else None
        result = JobResult(
            exit_code=exit_code,
            exit_message=exit_message,
            tcex=self.tcex,
            output_dir=self._output_dir,
        )

        resolved = profile.fetch_records(result)
        try:
            profile.assert_result(result, resolved)
        finally:
            profile.after(self, result)

        return result

    def _call_app_run(self, app: Any, profile: Profile) -> None:
        """Execute app.run() with all applicable context managers stacked.

        Handles env overrides, Choice field validation bypass (mock mode), and
        module-level SDK patching (patch_sdk_module_path) in a single ExitStack
        so the stack of patches is always consistent regardless of which flags
        are set.
        """
        env = profile.stage.env

        with ExitStack() as stack:
            # Temporarily inject profile.stage.env vars into the process environment.
            # Restored automatically after app.run() exits.
            stack.enter_context(patch.dict(os.environ, env))

            # In mock mode, Choice fields (e.g. ${OWNERS}) call GET /v3/security/owners
            # during App.__init__. Bypass that so mock tests don't need live TC owners data.
            if self.use_mock:
                stack.enter_context(self._choice_validation_bypass())

            # When an app imports and constructs its SDK at module level (not via injection),
            # patch the class itself so any internal construction gets the mock instead.
            if self.patch_sdk_module_path and self.sdk is not None:
                stack.enter_context(patch(self.patch_sdk_module_path, return_value=self.sdk))

            app.run()

    @contextmanager
    def _choice_validation_bypass(self):
        """Patch EditChoice to skip TC API calls for ${OWNERS} / ${ATTRIBUTE_TYPES} fields.

        Choice fields with validValues like ${OWNERS} call
        ThreatIntelUtil.resolve_variables which makes a live GET
        /v3/security/owners. validate_valid_values then checks:

            for vv in _valid_values:
                if vv.lower() == value.lower(): break
            else:
                if cls._allow_additional is False:
                    raise InvalidInput(...)

        Two patches together bypass this:
        1. resolve_variables: return static values as-is, skip TC API for ${...} vars.
        2. EditChoice._allow_additional: temporarily None so the else-branch is a no-op
           when no variable values match (avoids InvalidInput for ${OWNERS} fields).
        """
        def _resolve_passthrough(_self, inputs: list) -> list:
            # Strip ${...} variable refs — they require a live TC API call to expand
            return [v for v in inputs if v and not v.startswith('${')]

        with (
            # Skip the TC GET /v3/security/owners call used to populate valid values
            patch.object(ThreatIntelUtil, 'resolve_variables', _resolve_passthrough),
            # Allow any value through when the valid-values list is empty/unresolved
            patch.object(EditChoice, '_allow_additional', None),
        ):
            yield
