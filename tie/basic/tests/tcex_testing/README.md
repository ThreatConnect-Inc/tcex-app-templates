# tcex_testing

Shared test infrastructure for all TC Exchange app types. Provides assertion
primitives, TC object staging, fixture loading, and reference resolution —
with app-type-specific layers on top.

---

## Package home

`tcex_testing` is a shared Python package installed into each app's `deps_tests/`
via the test requirements file:

```
# tests/requirements.txt
tcex-testing @ git+https://github.com/your-org/tcex-testing.git
pytest
```

Each app installs deps_tests alongside its regular deps:

```bash
pip install -r tests/requirements.txt --target deps_tests/
PYTHONPATH=deps_tests:deps python3 -m pytest tests/ -v
```

The package does not bundle into the app distribution — it is a test-only
dependency.

---

## Package structure

```
tcex_testing/
├── checks.py          # Check — assertion primitives, shared by all app types
├── harness.py         # TestCaseBase — base lifecycle for all harnesses
├── resolver.py        # resolve_refs — ${env:}, ${vault:}, ${tc:} ref resolution
├── fixtures.py        # MockSDKMixin + load_fixture — shared fixture utilities
├── tc_stager.py       # TcStager — stage TC v3 objects and clean up after tests
│
└── apps/
    ├── playbook/      # Playbook (action) app test utilities
    ├── tie/           # TIE (FeedApiService) app test utilities
    └── job/           # Job (Organization) app test utilities
```

See `apps/<type>/README.md` for app-specific usage.

---

## Consistent pattern across all app types

All three app types use the same pattern: test class inherits from a harness
base, `self.run(profile)` runs the app and asserts results. No conftest, no
fixture injection.

For apps with a vendor SDK, define `create_sdk` and `create_mock_sdk` once in a
shared `AppTestCase` base (`tests/harness/base.py`). Individual test files
inherit from `AppTestCase`. Pure transform apps inherit the harness directly.

```python
# tests/harness/base.py
from tcex_testing.apps.playbook import PlaybookTestCase  # or JobTestCase / TieTestCase

class AppTestCase(PlaybookTestCase):
    use_mock = True

    def create_sdk(self): ...
    def create_mock_sdk(self): ...

# tests/test_enrich.py
from tests.harness.base import AppTestCase

class TestEnrich(AppTestCase):
    def test_basic(self):
        self.run(Profile(inputs={...}, expected=Expected(exit_codes=[0])))
```

| App type | Harness base | Profile type | Result type |
|----------|-------------|--------------|-------------|
| Playbook | `PlaybookTestCase` | `Profile` | `AppResult` |
| Job | `JobTestCase` | `Profile` | `JobResult` |
| TIE | `TieTestCase` | `Profile` (with `pipeline`) | per-stage result objects |

---

## Shared components

### `Check` — assertion primitives

The `Check` class is the single source of truth for non-equality assertions.
Used by all app types.

```python
from tcex_testing import Check

# type checks — singleton instances, no call needed
Check.is_string
Check.is_number
Check.is_bytes
Check.is_list
Check.is_dict
Check.is_json
Check.is_url
Check.is_date
Check.is_uuid
Check.is_ip
Check.is_base64
Check.is_bool_str
Check.is_not_empty

# string checks
Check.startswith(prefix)
Check.endswith(suffix)
Check.contains(substr)
Check.not_contains(substr)
Check.regex(pattern)

# numeric comparisons (value may be str or number)
Check.gt(n), Check.lt(n), Check.gte(n), Check.lte(n)
Check.between(low, high)

# collection checks
Check.length(n)
Check.length_gt(n), Check.length_gte(n), Check.length_lt(n), Check.length_lte(n)
Check.contains_item(item)
Check.in_list(values)
Check.all_match(check)

# binary
Check.hash_eq(sha256_hex)       # SHA256 of actual matches expected hex digest

# structural equality
Check.deep_diff(expected, ignore_order=False, exclude_paths=None)
Check.json_eq(expected)         # json.loads(actual) then deep_diff

# logical combinators
Check.not_(check)
Check.all_of(*checks)
Check.any_of(*checks)
```

---

### `TcStager` — TC object staging

Stage TC v3 objects before a test run and clean them up after. Shared by all
app types that need pre-existing TC data.

All three harnesses build the stager automatically via the built-in `_staging`
fixture. Tests just override `stage()` and call `self.stager.stage(...)` —
no manual setup needed.

```python
from tcex_testing import TcStager

# Built automatically by all harnesses — reads TC_API_PATH, TC_API_ACCESS_ID, TC_API_SECRET_KEY
stager = TcStager.from_env()

# stage objects — path is relative to /v3/
stager.stage('target', 'indicators/addresses', {'summary': '1.2.3.4', 'rating': 3})
stager.stage('report', 'groups/reports', {'name': 'Test Report'})
stager.stage('complex', 'indicators/addresses', {
    'summary': '10.0.0.1',
    'attributes': [{'type': 'Description', 'value': 'test desc'}],
    'associatedGroups': {'data': [{'id': 123}]},
})

# access staged object response data
indicator_id = stager.registry['target']['data']['id']

# cleanup — deletes in reverse creation order, tolerates 404s
stager.cleanup()
```

`stage()` stores the full TC API response under `key` in `stager.registry`.

Requires TC credentials in the environment:

```bash
export TC_API_ACCESS_ID=...
export TC_API_SECRET_KEY=...
export TC_API_PATH=https://your-tc-instance/api
```

---

### `resolve_refs` — reference resolution

Resolves `${env:}`, `${vault:}`, and `${tc:}` references recursively in dicts,
lists, or strings. Called automatically by `run()` and `setup()` in all
harnesses — most tests never need to call it directly.

```python
from tcex_testing import resolve_refs

inputs = resolve_refs(
    {'api_key': '${env:MY_API_KEY}', 'url': 'https://example.com'},
)
```

**`${env:NAME}`** — environment variable. Name is normalized to uppercase with
underscores; lookup is case-insensitive.

**`${vault:path/to/secret}`** — HashiCorp Vault KV. Requires `VAULT_ADDR` and
`VAULT_TOKEN` in the environment. KV v2 paths are rewritten automatically.

**`${tc:key.path}`** — staged TC object using JMESPath. `key` matches the key
passed to `TcStager.stage()`; `path` navigates the API response.

```python
# After stager.stage('target', 'indicators/addresses', {'summary': '1.2.3.4'})
stager.registry['target']['data']['id']     # direct access
# or via resolve_refs with staged= (used internally)
resolve_refs('${tc:target.data.id}', staged=stager.registry)  # → indicator ID
```

### `self.resolve()` — harness convenience wrapper

All harness classes expose `self.resolve(value, staged=None)` as a convenience
wrapper around `resolve_refs()`. Useful in `setup_method`, `teardown_method`,
`create_sdk()`, `create_mock_sdk()`, and `stage()` — anywhere `resolve_refs`
would be called but importing it separately is verbose.

```python
# In setup_method or SDK methods:
api_key = self.resolve('${env:MY_API_KEY}')
indicator_id = self.resolve('${tc:target.data.id}', staged=self.staged)

# Works with dicts too:
inputs = self.resolve({
    'api_key': '${env:MY_API_KEY}',
    'secret': '${vault:secret/my-app/key}',
})
```

`env` defaults to `os.environ` — no need to pass it explicitly.

---

### `StagedItem` / `Stage` — typed TC staging

`Stage.threatconnect` is a list of `StagedItem` — no more loose dicts.

```python
from tcex_testing import StagedItem
from tcex_testing.profile import Stage

stage=Stage(
    threatconnect=[
        StagedItem(key='target_ip', path='indicators/addresses', params={'summary': '1.2.3.4'}),
    ],
    env={'MY_FLAG': 'true'},
)
```

---

### `MockSDKMixin` — fixture-backed mock SDK mixin

Mixin for mock SDK implementations. `MockSDK` inherits from both `MockSDKMixin`
and the real SDK — `super().__init__()` runs the real SDK init so all non-HTTP
logic works. Only network methods are overridden to return data from `self._data`.

The harness calls `sdk._load_fixtures(self.fixture_paths)` automatically after
`create_mock_sdk()` returns — no fixture wiring in `MockSDK.__init__` needed.

```python
from tcex_testing import MockSDKMixin
from sdk.sdk import SDK


class MockSDK(MockSDKMixin, SDK):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_events(self, start, end):
        return self._data.get('events', [])
```

Fixture files are JSON files under `tests/fixtures/` using the three-level
convention. See any `apps/<type>/README.md` for the layout.

---

## Three test modes — all app types

Every app type supports the same three modes:

| Mode | What runs for real | When to use |
|------|--------------------|-------------|
| **Mock** | Transform logic | CI, every PR, no credentials |
| **Live (no upload)** | Vendor API + transform | Vendor credential CI gate or local dev |
| **Full E2E** | Vendor API + transform + TC upload | Pre-release or staging validation |

Mock tests are the default — no credentials, fast, catches transform regressions.
Live tests are gated by credential env vars and skip automatically if not set.
