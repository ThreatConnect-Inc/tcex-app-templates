# tcex_testing — Job apps (Organization)

Test infrastructure for TC Exchange Organization/Job apps. The test class IS the
harness — no fixture parameters needed.

| Mode          | Vendor SDK | TC Upload | Asserts against   | Credentials needed |
| ------------- | ---------- | --------- | ----------------- | ------------------ |
| `use_mock=True`  | Fixtures   | Real      | TC platform state | TC only            |
| `use_mock=False` | Real       | Real      | TC platform state | Vendor + TC        |

In both modes the app writes to the TC platform (or fails to connect in pure
offline environments). `FetchRecord` + `Check` assertions query TC after the run.

`JobResult` does **not** provide batch file assertion helpers — those are
commented out in `result.py` because not all job apps write batch files to disk.
If your app does, uncomment and adapt the helpers there.

---

## Directory layout

```
tests/
├── conftest.py              # required — sets cwd, sys.path (deps/, tests/, app root)
├── harness/
│   └── base.py              # AppTestCase — shared base (create_sdk, create_mock_sdk)
├── mock_sdk.py              # MockSDK — fixture-backed (lives in tests/, not harness/)
├── fixtures/
│   └── common/
│       └── events.json      # vendor API fixture data
└── test_events.py           # test classes inherit AppTestCase
```

`conftest.py` is required. It sets `os.chdir(APP_DIR)` and adds `deps/`,
`deps_tests/`, `tests/`, and app root to `sys.path`. Without it, imports fail.

---

## AppTestCase — shared base

Define `create_sdk` and `create_mock_sdk` once in `tests/harness/base.py`.
All test files inherit from `AppTestCase` — not from `JobTestCase` directly.

```python
# tests/harness/base.py
from tcex_testing.apps.job.base import JobTestCase


class AppTestCase(JobTestCase):
    use_mock = True  # default; override per-class or per-test

    def create_sdk(self):
        from sdk.sdk import SDK  # noqa: PLC0415
        return SDK(self.tcex.inputs.model, self.tcex, self.log)

    def create_mock_sdk(self):
        from mock_sdk import MockSDK  # noqa: PLC0415
        return MockSDK(self.tcex.inputs.model, self.tcex, self.log)
```

`MockSDK` is imported as `from mock_sdk import MockSDK` — not from
`tests.harness.mock_sdk`. The `tests/` directory is on `sys.path` via
`conftest.py`, so `mock_sdk` is importable directly.

Individual test files just inherit and write tests:

```python
# tests/test_events.py
from harness.base import AppTestCase
from tcex_testing.apps.job.profile import JobExpected, Profile


class TestEvents(AppTestCase):
    def test_run(self):
        result = self.run(Profile(inputs={'hours_back': '24'}))
```

Import paths:
- `Profile`, `JobExpected` → `from tcex_testing.apps.job.profile import JobExpected, Profile`
- `FetchRecord`, `Stage`, `StagedItem` → `from tcex_testing.profile import FetchRecord, Stage, StagedItem`
- `Check` → `from tcex_testing.checks import Check`

---

## SDK injection

`JobTestCase.run()` injects the mock or real SDK into the app after `App.__init__()`.
Default injection sets `app.sdk = sdk` via `_inject_sdk()`.

If the app imports and constructs the SDK at module level (e.g.
`from sdk.sdk import SDK` in `app.py`, constructed inside `App.__init__`),
attribute injection has no effect. Use `patch_sdk_module_path` instead:

```python
class AppTestCase(JobTestCase):
    patch_sdk_module_path = 'app.SDK'  # patches the class before app.run()
```

When `patch_sdk_module_path` is set, the harness calls
`patch(patch_sdk_module_path, return_value=self.sdk)` inside `_call_app_run()`.

---

## Mock SDK

`MockSDK` inherits from the real SDK and overrides only the methods that make
network calls. Non-HTTP logic (data conversion, batch upload, etc.) runs for real.

```python
# tests/mock_sdk.py
from sdk.sdk import SDK
from tcex_testing.fixtures import MockSDKMixin


class MockSDK(MockSDKMixin, SDK):
    def __init__(self, inputs, tcex, logger):
        # Call super().__init__ only if SDK.__init__ does not make network calls
        # or validate live credentials. If it does, initialize the minimum
        # required attributes manually instead.
        super().__init__(inputs, tcex, logger)

    def get_events(self, start, end) -> list:
        return self._data.get('events', [])
```

The harness calls `sdk._load_fixtures(self.fixture_paths)` automatically after
`create_mock_sdk()` returns — no fixture wiring needed in `MockSDK.__init__`.

`self._data` is a dict keyed by fixture filename stem. If `tests/fixtures/common/events.json`
exists, `self._data['events']` is the parsed list.

### When to skip `super().__init__()`

If the real SDK's `__init__` makes HTTP connections or reads sensitive credentials
before the app's input model is fully validated, calling `super().__init__()` will
fail. In that case, manually set the attributes the SDK methods need:

```python
def __init__(self, inputs, tcex, logger):
    self.tcex = tcex
    self.in_ = inputs
    self.log = logger
    # set any other attrs your overridden methods reference
```

### Fixture directory layout

```
tests/fixtures/
    common/                    # loaded for every test in every class
        events.json
    TestEvents/
        common/                # loaded for all TestEvents tests
            events.json        # overrides common/events.json for this class
        test_full_run/         # loaded only for TestEvents.test_full_run
            attributes.json
        test_empty/
            events.json        # empty list — overrides class common for this test
```

Fixture directories are resolved in this order:
1. `tests/fixtures/common/`
2. `tests/fixtures/{ClassName}/common/`
3. `tests/fixtures/{ClassName}/{test_method_name}/`

Later directories replace earlier ones for the same filename stem — no merging.
Only directories that exist are included; missing directories are silently skipped.

---

## Profile, JobExpected, FetchRecord

```python
from tcex_testing.apps.job.profile import JobExpected, Profile
from tcex_testing.profile import FetchRecord, Stage, StagedItem
from tcex_testing.checks import Check
```

```python
class StagedItem(BaseModel):
    key: str              # registry key — access at self.staged[key] or stager.registry[key]
    path: str             # TC v3 API path (e.g. 'indicators/addresses')
    body: dict = {}       # request body passed to POST /v3/{path}
    params: dict = {}     # query params controlling response shape (e.g. {'fields': ['tag']})

class Stage(BaseModel):
    threatconnect: list[StagedItem] = []
    env: dict[str, str] = {}

class FetchRecord(BaseModel):
    key: str              # label — referenced in checks via Check.on(key)
    path: str             # TC v3 API path (e.g. 'indicators/addresses')
    params: dict = {}     # query params — typically 'tql' and 'fields'

class JobExpected(FetchExpected):
    exit_codes: list[int] = [0]
    records: list[FetchRecord] = []     # TC API fetches to run after the app completes
    checks: list[CheckLike] = []        # ScopedCheck | Callable

class Profile(BaseModel):
    inputs: dict[str, Any]
    expected: JobExpected = JobExpected()
    stage: Stage = Stage()
    environments: list[str] = []
    before: Callable | None = None
    after: Callable | None = None
```

**`StagedItem.body` vs `StagedItem.params`**: `body` is the POST request body
(the TC object fields). `params` controls the TC API response shape, e.g.
`{'fields': ['tag', 'attribute']}`. Do not pass the creation body in `params`.

**`expected.exit_codes`**: defaults to `[0]`. To allow partial success, use
`exit_codes=[0, 3]`. The harness asserts `result.exit_code in exit_codes`.

**`environments`**: list of environment names that must be active for this test to
run. The harness checks `TCEX_TEST_ENVS` env var. If none of the listed environments
are in `TCEX_TEST_ENVS`, the test is skipped. Use for tests that require live TC
credentials (e.g. `environments=['local']`). Leave empty to always run.

**`records`** — each `FetchRecord` queries the TC v3 API after the app run and
stores the response `data` list under `record.key`. Use TQL filters to retrieve
exactly what the app uploaded.

**`checks`** — list of `ScopedCheck` (from `Check.on/all/any/count`) or plain
callables. Plain callables receive the full `resolved` dict (all fetched records
keyed by their `FetchRecord.key`).

---

## Stage — TC pre-staging and env overrides

`Stage.threatconnect` creates TC objects before the app runs and deletes them
after. `Stage.env` injects environment variables only during `app.run()`.

```python
stage=Stage(
    env={'APP_RUN_MODE': 'full'},
    threatconnect=[
        StagedItem(key='target_ip', path='indicators/addresses', body={'summary': '1.2.3.4', 'rating': 1}),
    ],
),
```

`Stage.threatconnect` items are created in `setup_method()` before the test
runs, not inside `run()`. The `stage()` method on the test class handles this.

### Class-level staging via `stage()`

Override `stage()` on the test class to pre-stage TC objects shared across all
tests in the class. Called once per test (in `setup_method`), cleaned up after:

```python
class TestWithPreStaging(AppTestCase):
    def stage(self) -> None:
        self.stager.stage(
            'existing_ip',
            'indicators/addresses',
            body={'summary': '10.20.30.40', 'rating': 1, 'confidence': 10},
        )
```

`stager.stage()` signature: `stage(key, path, body=None, params=None)`.
The staged object's full TC API response is stored at `self.staged[key]`.

---

## `_run_tag` — isolating live test data

Every test gets a unique `self._run_tag` (e.g. `tctest-a3f2c891`). Use it to
tag objects the app creates so you can fetch and assert only this test's data,
and clean up afterward without touching unrelated TC objects.

```python
def test_run_creates_indicators(self):
    self.run(Profile(
        inputs={**BASE_INPUTS, 'custom_tags': self._run_tag},
        expected=JobExpected(
            exit_codes=[0],
            records=[
                FetchRecord(
                    key='addresses',
                    path='indicators/addresses',
                    params={'tql': f'tag EQ "{self._run_tag}"', 'fields': 'tags'},
                ),
            ],
            checks=[
                Check.on('addresses').is_not_empty(),
            ],
        ),
        after=self._cleanup,
    ))

def _cleanup(self, *_) -> None:
    tql = f'tag EQ "{self._run_tag}"'
    for item in self.fetch('indicators/addresses', {'tql': tql}):
        self.tcex.session.tc.delete(f'/v3/indicators/{item["id"]}')
```

---

## `self.fetch()` — ad-hoc TC queries

Available on the test case for cleanup callbacks and ad-hoc assertions after
`run()`. Returns the `data` list from the TC v3 API response.

```python
records = self.fetch('indicators/addresses', params={'tql': 'summary EQ "1.2.3.4"'})
```

Requires an active TC session — call only after `self.run()`.

---

## Tests

One comprehensive example — mock SDK with TC upload, `JobExpected` assertions,
env override, per-test staging, run-tag isolation, and cleanup callback.

```python
# tests/test_events.py
import pytest
from harness.base import AppTestCase
from tcex_testing.apps.job.profile import JobExpected, Profile
from tcex_testing.checks import Check
from tcex_testing.profile import FetchRecord, Stage, StagedItem


BASE_INPUTS = {
    'api_key': '${env:VENDOR_API_KEY}',
    'url': 'https://vendor.example.com',
    'owner': 'Test Owner',
    # ... all required inputs
}


@pytest.mark.integration
class TestEvents(AppTestCase):
    use_mock = True  # fixture SDK; flip to False for live vendor

    def stage(self) -> None:
        """Pre-stage a TC indicator the app will update."""
        self.stager.stage(
            'existing_ip',
            'indicators/addresses',
            body={'summary': '10.20.30.40', 'rating': 1, 'confidence': 10},
        )

    def _cleanup(self, *_) -> None:
        tql = f'tag EQ "{self._run_tag}"'
        for item in self.fetch('indicators/addresses', {'tql': tql}):
            self.tcex.session.tc.delete(f'/v3/indicators/{item["id"]}')

    def test_full_run(self):
        result = self.run(Profile(
            inputs={**BASE_INPUTS, 'custom_tags': self._run_tag},
            environments=['local'],
            expected=JobExpected(
                exit_codes=[0],
                records=[
                    FetchRecord(
                        key='uploaded_ips',
                        path='indicators/addresses',
                        params={
                            'tql': f'tag EQ "{self._run_tag}"',
                            'fields': ['type', 'summary', 'rating', 'confidence'],
                        },
                    ),
                ],
                checks=[
                    Check.on('uploaded_ips').is_not_empty(),
                    Check.on('uploaded_ips').jmespath('[*].rating', Check.all_match(Check.gte(3))),
                    # Pre-staged IP should appear in results
                    lambda records: any(r['summary'] == '10.20.30.40' for r in records['uploaded_ips']),
                ],
            ),
            stage=Stage(
                env={'APP_RUN_MODE': 'full'},
                threatconnect=[
                    StagedItem(key='related_group', path='groups/reports', body={'name': 'Baseline Report'}),
                ],
            ),
            after=self._cleanup,
        ))


class TestNoData(AppTestCase):
    """App runs cleanly when the SDK returns no data."""

    def test_run_no_data(self):
        self.run(Profile(
            inputs={**BASE_INPUTS},
            expected=JobExpected(exit_codes=[0, 3]),
        ))
```

---

## `JobResult` reference

`run()` returns a `JobResult`. It exposes:

```python
result.exit_code      # int — app exit code
result.exit_message   # str | None — contents of message.tc, if written
result.tcex           # TcEx instance — access result.tcex.session.tc for raw API calls
```

There are no built-in batch file assertion methods. If the app writes batch
`.json.gz` files, uncomment the helpers in `result.py` and adapt to your layout.

Exit code and exit message assertions run automatically from `profile.expected`
before `run()` returns — no explicit assertion needed.

---

## `Check` reference

All `Check` factory methods return a `CheckOp`. Scoped variants (`Check.on`,
`Check.all`, `Check.any`, `Check.count`) return `ScopedCheck` for use in `checks` lists.

```python
# Type checks
Check.is_string(), Check.is_number(), Check.is_list(), Check.is_dict()
Check.is_url(), Check.is_date(), Check.is_uuid(), Check.is_ip()
Check.is_not_empty()

# String
Check.startswith(prefix), Check.endswith(suffix)
Check.contains(substring), Check.not_contains(substring)
Check.regex(pattern)

# Numeric
Check.gt(n), Check.lt(n), Check.gte(n), Check.lte(n), Check.between(low, high)

# Collections
Check.length(n), Check.length_gt(n), Check.length_gte(n)
Check.contains_item(item), Check.in_list(lst), Check.all_match(check_op)

# Structural
Check.jmespath(expression, expected)   # expected can be a value, CheckOp, or callable
Check.deep_diff(expected, ignore_order=False)

# Logical
Check.not_(check_op), Check.all_of(*check_ops), Check.any_of(*check_ops)

# Scoped — for checks lists
Check.on(key).method(...)   # applied to resolved[key]
Check.all().method(...)     # applied to every record; all must pass
Check.any().method(...)     # applied to every record; at least one must pass
Check.count(min=N, max=M)   # total item count across all resolved records
```

`Check.on(key).jmespath(expression, expected)` extracts via jmespath from the
list stored at `resolved[key]`, then asserts against `expected`.

`Check.on(key).all_match(check_op)` asserts that `check_op` passes for every
item in `resolved[key]`.

---

## `before` / `after` callbacks

`Profile.before` and `Profile.after` are callables invoked around `app.run()`.

```python
Profile(
    inputs={...},
    before=lambda case: case.stager.stage('extra', 'groups/reports', body={'name': 'Pre-run'}),
    after=self._cleanup,
)
```

`before(test_case)` — receives the test case instance, called after SDK
injection but before `app.run()`.

`after(test_case, result)` — receives the test case instance and `JobResult`,
called after `profile.assert_result()`. Use for TC cleanup.

---

## Running tests

```bash
# mock mode — no live credentials needed
pytest tests/ -v

# live TC — requires TC_API_PATH, TC_API_ACCESS_ID, TC_API_SECRET_KEY
TCEX_TEST_ENVS=local TC_API_PATH='...' TC_API_ACCESS_ID='...' TC_API_SECRET_KEY='...' \
  pytest tests/ -v

# live vendor + TC
TCEX_TEST_ENVS=local VENDOR_API_KEY='...' TC_API_PATH='...' TC_API_ACCESS_ID='...' TC_API_SECRET_KEY='...' \
  pytest tests/ -v
```

`TCEX_TEST_ENVS` is a comma-separated list of active environment names. Tests
with `environments=['local']` are skipped unless `local` appears in this list.

`TCEX_TESTING_NO_CLEANUP=1` skips TC object deletion after tests — useful for
inspecting staged objects in TC when debugging.

---

## What NOT to do

- **Do not inherit from `JobTestCase` directly in test files.** Always go through
  `AppTestCase` in `tests/harness/base.py`. `JobTestCase` is abstract.

- **Do not define `__init__` on test classes.** pytest skips collection on
  classes with `__init__`. Use `setup_method` or `stage()` instead.

- **Do not call `_load_fixtures()` in `MockSDK.__init__`.** The harness calls
  it automatically. Calling it again in `__init__` loads empty data (fixture
  paths aren't known yet).

- **Do not use `StagedItem.params` for the TC object body.** `params` is for
  query parameters controlling the TC API response. The object fields go in `body`.

- **Do not fetch TC records in `stage()`.** `self.tcex` is `None` during
  `stage()`. Use `self.stager.registry[key]` to access staged object responses.

- **Do not assert TC platform state in `use_mock=True` tests without TC
  credentials.** `FetchRecord` queries the TC API. If `TC_API_PATH` is not set,
  these fetches will fail even in mock mode. Reserve `FetchRecord` checks for
  tests that require live TC credentials (gate them with `environments`).
