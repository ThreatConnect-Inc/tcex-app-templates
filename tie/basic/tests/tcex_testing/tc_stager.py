"""TcStager — stage TC objects before a test run and clean them up after.

Used by all app types that need pre-existing TC data (indicators, groups, cases, etc.)
before the app under test runs. Staged objects can be referenced in inputs via
${tc:key.path} JMESPath expressions resolved by the resolver.

Prerequisites:
    TC_API_PATH, TC_API_ACCESS_ID, TC_API_SECRET_KEY, and TC_OWNER must be set
    in the environment before running any tests that use staging.

Usage:
    stager = TcStager()

    stager.stage('target', 'indicators/addresses', body={'summary': '1.2.3.4', 'rating': 3})
    stager.stage('report', 'groups/reports', body={'name': 'Test Report'})
    stager.stage('empty_case', 'cases')  # body defaults to {}

    # reference in inputs
    inputs = resolver.resolve({'indicator_id': '${tc:target.data.id}'})

    # after test
    stager.cleanup()

Path convention:
    Always relative to /v3/ — stager prepends it.
    'indicators/addresses'  → POST /v3/indicators/addresses
    'groups/reports'        → POST /v3/groups/reports
    'cases'                 → POST /v3/cases
"""

# standard library
import os

# third-party
import requests
from tcex import TcEx


class TcStager:
    """Stage TC v3 objects and clean them up after a test run.

    Requires TC_API_PATH, TC_API_ACCESS_ID, TC_API_SECRET_KEY, and TC_OWNER
    to be set in the environment. Fails at construction if they are absent.

    Prefer TcStager.from_env() over direct construction — it degrades to a
    no-op stager when TC credentials are absent, so mock/unit runs work
    without a live ThreatConnect instance.
    """

    @staticmethod
    def from_env() -> 'TcStager | _NoOpStager':
        """Return a real stager when TC credentials are present, else a no-op.

        Constructing TcStager directly builds a TcEx session from TC_API_*
        environment variables and raises KeyError when they are unset. Mock
        and unit test runs have no credentials and stage nothing, so they get
        a _NoOpStager that satisfies the same interface without API calls.
        """
        if not os.environ.get('TC_API_ACCESS_ID'):
            return _NoOpStager()
        return TcStager()

    def __init__(self) -> None:
        self._session = self._build_session()
        self._base_url = os.environ['TC_API_PATH'].rstrip('/')
        self._registry: dict[str, dict] = {}
        self._cleanup_queue: list[str] = []

    @staticmethod
    def _build_session() -> requests.Session:
        """Build an authenticated TC API session using TcEx from environment variables."""
        tcex = TcEx(config={
            'tc_api_path': os.environ['TC_API_PATH'],
            'tc_api_access_id': os.environ['TC_API_ACCESS_ID'],
            'tc_api_secret_key': os.environ['TC_API_SECRET_KEY'],
            'tc_log_level': 'warning',
        })
        # `session.tc`, NOT `session.external`. The external session is the plain vendor
        # session — retries and proxies but no TC HMAC signing — so every staging call
        # 401'd while the three TC credentials above were read only to build a TcEx whose
        # authenticated session was then discarded.
        return tcex.session.tc

    # -- Public interface ------------------------------------------------------

    def stage(
        self,
        key: str,
        path: str,
        body: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """POST to /v3/{path}, register response under key, queue for cleanup.

        Args:
            key:    Identifier used to reference this object in ${tc:key.field} refs.
            path:   TC v3 path without the /v3/ prefix, e.g. 'indicators/addresses'.
            body:   Request body dict. Defaults to empty — useful when staging an object
                    that requires no fields (e.g. a case with all defaults).
            params: Query parameters passed to the TC API. Use to control response shape,
                    e.g. {'fields': ['attribute', 'tag']} to include related data.

        Returns:
            Full TC API response dict.
        """
        full_path = f'/v3/{path}'
        response = self._post(full_path, body or {}, params or {})
        self._registry[key] = response
        object_id = response['data']['id']
        self._cleanup_queue.append(f'{full_path}/{object_id}')
        return response

    def cleanup(self) -> None:
        """Delete all staged objects in reverse creation order.

        Set TCEX_TESTING_NO_CLEANUP=1 to skip deletion — useful when you need
        to inspect staged objects in TC after a test run.
        """
        if os.environ.get('TCEX_TESTING_NO_CLEANUP'):
            return
        for path in reversed(self._cleanup_queue):
            self._delete(path)
        self._registry.clear()
        self._cleanup_queue.clear()

    def get(self, key: str) -> dict:
        """Return the stored API response for a staged object by key."""
        if key not in self._registry:
            raise KeyError(f'No staged object with key {key!r}')
        return self._registry[key]

    @property
    def registry(self) -> dict[str, dict]:
        """Read-only view of all staged responses, keyed by stage key."""
        return dict(self._registry)

    # -- Private ---------------------------------------------------------------

    def _post(self, path: str, body: dict, params: dict) -> dict:
        url = f'{self._base_url}{path}'
        response = self._session.post(url, json=body, params=params)
        response.raise_for_status()
        return response.json()

    def _delete(self, path: str) -> None:
        url = f'{self._base_url}{path}'
        response = self._session.delete(url)
        # 404 is acceptable — object may have been deleted by the app under test
        if response.status_code not in (200, 204, 404):
            response.raise_for_status()


class _NoOpStager:
    """Stand-in for TcStager when no TC credentials are available.

    Satisfies the TcStager interface used by TestCaseBase (stage/cleanup/get/
    registry) but makes no API calls. Returned by TcStager.from_env() so that
    mock and unit test runs — which never stage real TC objects — do not need
    TC_API_* environment variables set.

    stage() raises rather than silently succeeding: a test that actually stages
    an object needs real credentials, and quietly returning an empty response
    would surface later as a confusing ${tc:} resolution failure.
    """

    def __init__(self) -> None:
        self._registry: dict[str, dict] = {}

    def stage(
        self,
        key: str,
        path: str,
        body: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """Reject staging attempts — real staging requires TC credentials."""
        raise RuntimeError(
            f'Cannot stage {key!r} at {path!r}: TC credentials are not configured. '
            'Set TC_API_PATH, TC_API_ACCESS_ID, TC_API_SECRET_KEY, and TC_OWNER '
            'to run tests that stage ThreatConnect objects.'
        )

    def cleanup(self) -> None:
        """No-op — nothing was ever staged."""

    def get(self, key: str) -> dict:
        """Always raises — no objects can be staged without credentials."""
        raise KeyError(f'No staged object with key {key!r}')

    @property
    def registry(self) -> dict[str, dict]:
        """Always empty."""
        return {}
