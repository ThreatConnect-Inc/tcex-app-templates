"""TestCaseBase — shared lifecycle foundation for all app-type test cases.

JobTestCase, TieTestCase, and PlaybookTestCase all extend this. Provides:
  - sys.path setup (deps/ priority for pydantic v1 apps)
  - TcEx instance construction helper
  - Temp output dir management
  - setup_method() base that creates self.resolver, self.stager, and calls self.stage()
  - teardown_method() base that calls self.stager.cleanup()
"""

# standard library
import inspect
import logging
import os
import sys
import tempfile
from abc import ABC
from pathlib import Path
from typing import Any
from uuid import uuid4

from tcex import TcEx
from tcex_testing.resolver import Resolver
from tcex_testing.tc_stager import TcStager


class TestCaseBase(ABC):
    """Generic base for all app-type test cases.

    Pytest collects test classes by scanning their MRO for __init__ — any class
    that defines __init__ is skipped with PytestCollectionWarning. This class
    uses setup_method() as the per-test initializer instead.

    Subclasses call super().setup_method(method) first, then do their own setup.
    Similarly, subclasses call super().teardown_method(method) in teardown.
    """

    # Class-level defaults — overridden per-instance in setup_method.
    tcex: Any = None
    log: Any = None
    resolver: Resolver
    # May be a _NoOpStager when TC credentials are absent — see TcStager.from_env().
    stager: Any
    _output_dir: Path
    _current_test_name: str = ''
    _run_tag: str = ''

    # Set True on test classes that need a vendor SDK to use the mock instead.
    # Apps with no SDK ignore this entirely.
    use_mock: bool = False

    @property
    def app_dir(self) -> Path:
        """App root — two levels up from the concrete test class file.

        Assumes tests live in <app_root>/tests/. Override if the layout differs.
        """
        return Path(inspect.getfile(type(self))).parent.parent

    # -- Lifecycle -------------------------------------------------------------

    def setup_method(self, method: Any = None) -> None:
        """Per-test setup. Resets state, sets up paths, creates resolver and stager.

        Subclasses must call super().setup_method(method) before their own setup.
        """
        self._current_test_name = method.__name__ if method is not None else ''
        self._output_dir = Path(tempfile.mkdtemp())
        self._run_tag = f'tctest-{uuid4().hex[:8]}'
        os.environ['TCEX_RUN_TAG'] = self._run_tag
        self.tcex = None
        self.log = None
        self._setup_paths()
        self.tc_owner = os.environ.get('TC_OWNER', 'TCI')
        self.stager = TcStager.from_env()
        self.stage()
        self.resolver = Resolver(staged=self.stager.registry)

    def teardown_method(self, *_) -> None:
        """Per-test teardown. Cleans up staged TC objects.

        Subclasses must call super().teardown_method() after their own teardown.
        """
        os.environ.pop('TCEX_RUN_TAG', None)
        self.stager.cleanup()

    def stage(self) -> None:
        """Override to stage TC objects needed by this test.

        Called automatically in setup_method before each test. Use self.stager
        to create TC objects — they are cleaned up automatically after the test.

            def stage(self):
                self.stager.stage('target', 'indicators/addresses', body={'summary': '1.2.3.4'})
        """

    @property
    def staged(self) -> dict:
        """Shortcut for self.stager.registry — the dict of staged TC objects."""
        return self.stager.registry

    def resolve(self, value: Any) -> Any:
        """Resolve ${env:}, ${vault:}, and ${tc:} refs in value."""
        return self.resolver.resolve(value)

    def fetch(self, path: str, params: dict | None = None) -> list:
        """Fetch TC v3 records at path with optional query params.

        Same mechanic as FetchRecord in profiles — returns the 'data' list
        from the TC API response.

            records = self.fetch('indicators/addresses', params={'tql': 'summary EQ "1.2.3.4"'})
            Check.is_not_empty()(records)
            Check.jmespath('[0].rating', 3)(records)
        """
        assert self.tcex is not None, 'fetch() requires an active tcex session — call run() first'
        response = self.tcex.session.tc.get(f'/v3/{path}', params=params or {})
        response.raise_for_status()
        return response.json().get('data', [])

    def teardown(self) -> None:
        """Override for app-specific cleanup beyond TC object deletion."""

    # -- Fixture resolution ----------------------------------------------------

    def _resolve_fixture_paths(self, test_name: str) -> list[Path]:
        """Resolve fixture directories for the current test in load order.

        Load order (later overrides earlier for the same filename stem):
          1. tests/fixtures/common/
          2. tests/fixtures/{ClassName}/common/
          3. tests/fixtures/{ClassName}/{test_name}/

        Only directories that exist are included.
        """
        base = Path(self.app_dir) / 'tests' / 'fixtures'
        class_name = type(self).__name__
        candidates = [
            base / 'common',
            base / class_name / 'common',
            base / class_name / test_name,
        ]
        return [p for p in candidates if p.exists()]

    @property
    def fixture_paths(self) -> list[Path]:
        """Resolved fixture directories for the currently running test."""
        return self._resolve_fixture_paths(self._current_test_name)

    # -- SDK injection ---------------------------------------------------------

    def _inject_sdk(self, app: object, sdk: object) -> None:
        """Set the SDK instance on an already-instantiated app object.

        Default assumes the app has a 'sdk' attribute. Override if the app
        uses a different attribute name:

            def _inject_sdk(self, app, sdk):
                app.client = sdk
        """
        app.sdk = sdk  # type: ignore[attr-defined]

    # -- Shared helpers (called by subclass setup_method) ----------------------

    def _setup_paths(self) -> None:
        """Insert deps/ and app_dir into sys.path (deps first for pydantic v1)."""
        deps = str(self.app_dir / 'deps')
        app = str(self.app_dir)
        if deps not in sys.path:
            sys.path.insert(0, deps)
        if app not in sys.path:
            sys.path.insert(0, app)

    def _setup_tcex(self, inputs: dict) -> None:
        """Build TcEx instance from the provided inputs dict."""
        self._output_dir.mkdir(parents=True, exist_ok=True)

        inputs = dict(inputs)
        inputs.setdefault('tc_out_path', str(self._output_dir))
        inputs.setdefault('tc_in_path', str(self._output_dir))
        inputs.setdefault('tc_log_path', str(self._output_dir))
        inputs.setdefault('tc_temp_path', str(self._output_dir))
        inputs.setdefault('tc_log_level', 'warning')

        for key in ('tc_api_path', 'tc_api_access_id', 'tc_api_secret_key'):
            env_val = os.environ.get(key.upper())
            if env_val:
                inputs.setdefault(key, env_val)

        self.tcex = TcEx(config=inputs)

    def _setup_logging(self) -> None:
        self.log = self.tcex.log
        self.log.setLevel(logging.DEBUG)
