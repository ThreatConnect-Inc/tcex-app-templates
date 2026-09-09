# tcex_testing — Playbook apps

Test infrastructure for TcEx playbook action apps. Tests run the app inline,
in-process — no subprocess, no Redis required.

## Overview

For apps with a vendor SDK, define `create_sdk` and `create_mock_sdk` once in
a shared `AppTestCase` base. All test files inherit from that — not from
`PlaybookTestCase` directly.

Pure transform apps (no SDK) can inherit `PlaybookTestCase` directly — no base
needed.

```
tests/
├── harness/
│   ├── base.py          # AppTestCase — shared base (create_sdk, create_mock_sdk)
│   └── mock_sdk.py      # MockSDK — fixture-backed
├── fixtures/            # vendor API fixture data (three-level convention)
├── test_enrich.py       # inherit AppTestCase
├── test_lookup.py       # inherit AppTestCase
└── test_convert.py      # pure transform — inherit PlaybookTestCase directly
```

The framework:

- Runs the app inline, same process, no subprocess
- KV I/O uses an in-memory store (bypasses Redis entirely)
- Resolves `${env:}` and `${vault:}` refs in inputs automatically
- Harness state is reset per test (fresh TcEx, fresh output dir)
- Assertions run automatically inside `run()` — no separate assert call needed

---

## AppTestCase — shared base

For apps that call a vendor SDK, define `create_sdk` and `create_mock_sdk` once
in `tests/harness/base.py`. All test files inherit from `AppTestCase`.

```python
# tests/harness/base.py
from tcex_testing.apps.playbook import PlaybookTestCase


class AppTestCase(PlaybookTestCase):
    use_mock = True  # default; override per-class or per-test

    def create_sdk(self):
        from sdk.sdk import VendorSDK
        return VendorSDK(api_key=self.resolve('${vault:secret/vendor#api_key}'))

    def create_mock_sdk(self):
        from tests.harness.mock_sdk import MockVendorSDK
        return MockVendorSDK(api_key=self.resolve('${vault:secret/vendor#api_key}'))
```

Pure transform test classes (no SDK) inherit `PlaybookTestCase` directly —
no base needed, no `create_sdk`/`create_mock_sdk` required.

---

## Tests

One comprehensive example showing all features wired together: vault-resolved
credentials, mock SDK, class-level TC staging, per-test staging via
`Profile.stage`, env override, `before=` / `after=` hooks, and
`Expected.outputs` with exact values, `None` checks, and `Check` instances.

```python
# tests/test_enrich.py
from tcex_testing.profile import Profile, Stage, Expected
from tcex_testing import Check, StagedItem
from tests.harness.base import AppTestCase


# Inheritance — define a base outputs helper, override specific keys in subclasses:
#
#   class TestEnrich(AppTestCase):
#
#       def base_outputs(self, **overrides) -> dict:
#           return {
#               'outputs.enrich.action': 'Enrich Indicator',
#               'outputs.enrich.indicator.rating': Check.gte(1),
#               'outputs.enrich.indicator.summary': Check.is_not_empty,
#               **overrides,
#           }
#
#       def test_standard(self):
#           self.run(Profile(inputs={...}, expected=Expected(outputs=self.base_outputs())))
#
#   class TestEnrichHighConfidence(TestEnrich):
#       def test_high_confidence_source(self):
#           self.run(Profile(
#               inputs={...},
#               expected=Expected(outputs=self.base_outputs(
#                   **{'outputs.enrich.indicator.rating': Check.gte(4)},  # override
#                   **{'outputs.enrich.indicator.source': 'premium'},      # add
#               )),
#           ))
#
class TestEnrichIndicator(AppTestCase):
    """Full test — vault creds + TC staging + mock SDK + output checks."""

    # Class-level run mode. To run live for a specific test, override setup_method:
    #   def setup_method(self, _method=None):
    #       self.use_mock = not os.environ.get('LIVE_TEST')
    #       super().setup_method(_method)
    use_mock = True

    # ── Class-level TC staging (once per class, auto cleaned up) ─────────────

    def stage(self) -> None:
        self.stager.stage(
            key='target_ip',
            path='indicators/addresses',
            params={'summary': '1.2.3.4', 'rating': 1},
        )
        self.stager.stage(
            key='related_group',
            path='groups/reports',
            params={'name': 'Known Campaign'},
        )

    # ── Tests ─────────────────────────────────────────────────────────────────

    def test_enrich_indicator(self):
        """
        Demonstrates all features in one test:
          - vault-resolved API key (create_sdk / create_mock_sdk)
          - class-level staged TC indicator (target_ip from stage())
          - per-test TC staging via Profile.stage
          - before= hook to validate pre-run state
          - after= hook for post-run custom assertion
          - Expected.outputs with exact values, None, and Check instances
        """
        def before_run(test_case):
            assert test_case.staged['target_ip']['data']['summary'] == '1.2.3.4'

        def after_run(test_case, result):
            # Custom assertion not expressible via Expected.outputs
            assert result.exit_message is not None

        # inputs are fed through TcEx AppInputs (pydantic) validation inside run()
        self.run(Profile(
            inputs={
                'tc_action': 'Enrich Indicator',
                'indicator_id': self.staged['target_ip']['data']['id'],
                'api_base_url': '${vault:secret/vendor#base_url}',
            },
            expected=Expected(
                exit_codes=[0],
                exit_message='Successfully enriched indicator.',
                outputs={
                    'outputs.enrich.action': 'Enrich Indicator',
                    'outputs.enrich.indicator.summary': '1.2.3.4',
                    'outputs.enrich.indicator.rating': Check.gte(3),
                    'outputs.enrich.indicator.confidence': Check.between(50, 100),
                    'outputs.enrich.indicator.last_seen': Check.is_date,
                    'outputs.enrich.indicator.tags': Check.is_not_empty,
                    'outputs.enrich.indicator.error': None,    # assert field not written
                    'outputs.enrich.raw_json': Check.is_json,
                },
            ),
            stage=Stage(
                threatconnect=[
                    StagedItem(key='context_group', path='groups/incidents', params={'name': 'Active Incident'}),
                ],
            ),
            before=before_run,
            after=after_run,
        ))
```

- `run(profile)` runs the app, asserts all expectations, and returns `AppResult`
- All assertions happen inside `run()` — failures raise immediately with a clear
  message
- `exit_codes` is a list; pass multiple codes to allow any of them

---

## Profile, Stage, Expected

```python
from tcex_testing.profile import Profile, Stage, Expected
```

### `Profile`

```python
class Profile(BaseModel):
    inputs: dict[str, Any]
    expected: Expected = Expected()
    stage: Stage = Stage()
    before: Callable | None = None   # called before app run, receives test instance
    after: Callable | None = None    # called after app run, receives (test instance, AppResult)
```

### `Expected`

```python
class Expected(BaseModel):
    exit_codes: list[int] = [0]
    exit_message: str | None = None
    outputs: dict[str, Any] | None = None
```

`outputs` is a dict of `variable_name → expected_value`. Values can be plain
equality, a `Check` instance, or `None` (asserts the variable was not written).

### `Stage`

```python
class StagedItem(BaseModel):
    key: str           # registry key — access at stager.registry[key]
    path: str          # TC v3 API path (e.g. 'indicators/addresses')
    params: dict = {}  # request body

class Stage(BaseModel):
    threatconnect: list[StagedItem] = []
    env: dict[str, str] = {}
```

Staged objects are available at `self.staged[key]` (i.e. `stager.registry[key]`).

---

## Result object

`AppResult` is returned by `self.run()`.

```python
result = self.run(Profile(...))

result.exit_code        # int
result.exit_message     # str | None
result.output(name)     # Any — output variable by clean name

result.assert_exit_code(n)          # raise if exit code != n
result.assert_output(name, expected)  # raise if output != expected
```

Use `result.output()` and `result.assert_output()` for additional checks after
`run()` returns, or inspect `result.exit_message` directly.

```python
def test_hash(self):
    result = self.run(Profile(
        inputs={'tc_action': 'Hash', 'input_binary': b'hello world'},
        expected=Expected(
            exit_codes=[0],
            outputs={'md5': Check.is_string, 'sha256': Check.length(64)},
        ),
    ))
    # Extra post-run checks:
    result.assert_output('sha1', Check.length(40))
    assert result.exit_message is not None
```

---

## SDK mock pattern

Playbook apps that call a vendor SDK use `MockSDKMixin` in `tests/harness/mock_sdk.py`
and wire it up once in `AppTestCase`:

```python
# tests/harness/mock_sdk.py
from tcex_testing import MockSDKMixin
from sdk.sdk import VirusTotalSDK


class MockVirusTotalSDK(MockSDKMixin, VirusTotalSDK):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def lookup_hash(self, file_hash: str) -> dict:
        return self._data.get('vt_malicious_response', {})


# tests/harness/base.py
from tcex_testing.apps.playbook import PlaybookTestCase
from tests.harness.mock_sdk import MockVirusTotalSDK
from sdk.sdk import VirusTotalSDK


class AppTestCase(PlaybookTestCase):
    use_mock = True  # flip to False for live tests

    def create_sdk(self):
        return VirusTotalSDK(api_key=self.resolve('${env:VT_API_KEY}'))

    def create_mock_sdk(self):
        return MockVirusTotalSDK(api_key=self.resolve('${env:VT_API_KEY}'))


# tests/test_lookup.py
from tcex_testing.profile import Profile, Expected
from tests.harness.base import AppTestCase


class TestVirusTotalLookup(AppTestCase):
    def test_known_malicious(self):
        self.run(Profile(
            inputs={'tc_action': 'Lookup Hash', 'file_hash': 'abc123...'},
            expected=Expected(
                exit_codes=[0],
                outputs={'is_malicious': 'true'},
            ),
        ))
```

The harness sets `app.sdk = sdk` after instantiation.

**Pure transform apps** (Base64, Hash, etc.) don't override either method — they
return `None` by default and `run()` skips patching entirely. No `use_mock`
needed.

The three test modes apply to playbook apps just as they do for job/TIE:

| `use_mock`        | What runs                       | Mode                  |
| ----------------- | ------------------------------- | --------------------- |
| `True`            | `create_mock_sdk()` — fixtures  | Mock — no credentials |
| `False`           | `create_sdk()` — real vendor API | Live — vendor creds  |
| Both `None`       | No SDK                          | Pure transform        |

---

## Reference resolution

Input values support `${env:}` and `${vault:}` refs — resolved automatically
inside `run()`:

```python
self.run(Profile(
    inputs={
        'tc_action': 'My Action',
        'api_key': '${env:MY_API_KEY}',         # from environment
        'secret': '${vault:secret/my-app/key}', # from HashiCorp Vault
    },
    expected=Expected(exit_codes=[0]),
))
```

Outside of `run()` — in `setup_method`, `teardown_method`, `create_mock_sdk()`,
or `create_sdk()` — use `self.resolve()`:

```python
def create_sdk(self):
    return VirusTotalSDK(api_key=self.resolve('${env:VT_API_KEY}'))

def setup_method(self, method=None):
    super().setup_method(method)
    self._detector_id = self.resolve('${env:GD_DETECTOR_ID}')
```

---

## Check reference

See the top-level `tcex_testing` README for the full `Check` reference. Commonly
used in playbook tests:

```python
# type checks (singletons — no call needed)
Check.is_string
Check.is_bytes
Check.is_number
Check.is_list
Check.is_not_empty

# string checks
Check.contains('substr')
Check.startswith('prefix')
Check.endswith('suffix')
Check.regex(r'pattern')

# numeric comparisons
Check.gt(0)
Check.gte(1)
Check.between(1, 5)

# collection
Check.length(n)
Check.length_gte(1)

# binary
Check.hash_eq('sha256_hex_digest...')

# equality helpers
Check.deep_diff({'key': 'value'})
Check.json_eq({'key': 'value'})      # for !String outputs containing JSON

# logical
Check.all_of(Check.is_string, Check.startswith('ok'))
Check.any_of(Check.is_number, Check.is_bool_str)
Check.not_(Check.is_number)
```

---

## Running tests

```bash
# full suite
PYTHONPATH=deps_tests:deps python3 -m pytest tests/ -v

# single test class
pytest tests/test_convert_from_base64.py::TestConvertFromBase64 -v

# single test method
pytest tests/test_hash.py::TestHashSingle::test_basic -v
```
