# tcex_testing — TIE apps (FeedApiService)

Test infrastructure for TIE (`tcvf-*`) apps. Tests drive pipeline stages —
Download, Convert, Upload — using a declarative `Profile` + `PipelineTask`
structure. Fixture-backed mock SDKs for unit tests; real vendor API for
integration tests.

| Mode             | Vendor SDK | TC Upload      | Credentials needed |
| ---------------- | ---------- | -------------- | ------------------ |
| `use_mock=True`  | Fixtures   | Stubbed        | None               |
| Live (no upload) | Real       | No upload step | Vendor only        |
| Live E2E         | Real       | Real           | Vendor + TC        |

---

## Directory layout

```
tests/
├── harness/
│   ├── base.py              # AppTestCase — shared base (all abstract methods once)
│   └── mock_sdk.py          # MockSDK — fixture-backed
├── fixtures/
│   ├── sightings.json       # raw vendor API responses
│   └── reports.json
└── test_pipeline.py         # test classes inherit AppTestCase
```

No `conftest.py` needed. The `_staging` fixture is built into `TieTestCase`.

---

## AppTestCase — shared base

Implement all five abstract methods once in `tests/harness/base.py`. All test
files inherit from `AppTestCase`.

```python
# tests/harness/base.py
from tcex_testing.apps.tie import TieTestCase
from tcex_testing.resolver import resolve_refs


class AppTestCase(TieTestCase):
    use_mock = True  # default; override per-class or per-test

    def create_inputs(self) -> dict:
        return {'tc_owner': self.tc_owner}

    def create_settings(self):
        from model.settings_model import SettingModel
        token = resolve_refs('${vault:secret/vendor#api_key}')
        return SettingModel(bearer_token=token, base_path=self._output_dir, tc_owner=self.tc_owner)

    def create_sdk(self):
        from sdk.sdk import SDK
        token = resolve_refs('${vault:secret/vendor#api_key}')
        return SDK(self.tcex, self.log, token)

    def create_mock_sdk(self):
        from tests.harness.mock_sdk import MockSDK
        token = resolve_refs('${vault:secret/vendor#api_key}')
        return MockSDK(self.tcex, self.log, token)

    def create_job_request(self, updated_since, updated_till, **kwargs):
        from model.job_request_model import JobRequestModel
        return JobRequestModel(updated_since=updated_since, updated_till=updated_till, **kwargs)
```

---

## Mock SDK

`MockSDK` inherits from the real SDK and calls `super().__init__()` so all
non-HTTP logic runs for real. Only the methods that make network calls are
overridden to return fixture data from `self._data`.

```python
from tcex_testing import MockSDKMixin
from sdk.sdk import SDK


class MockSDK(MockSDKMixin, SDK):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def sightings(self, start_time, end_time):
        yield from self._data.get('sightings', [])

    def reports(self, start_time, end_time):
        yield from self._data.get('reports', [])

    def test_connection(self):
        return True
```

The harness calls `_load_fixtures(self.fixture_paths)` automatically after
`create_mock_sdk()` returns. `create_mock_sdk` just passes the same args as
`create_sdk`:

```python
def create_sdk(self):
    from sdk.sdk import SDK
    token = resolve_refs('${vault:secret/myapp#api_key}')
    return SDK(self.tcex, self.log, token)

def create_mock_sdk(self):
    from tests.harness.mock_sdk import MockSDK
    token = resolve_refs('${vault:secret/myapp#api_key}')
    return MockSDK(self.tcex, self.log, token)
```

### Fixture directory layout

```
tests/fixtures/
    common/                    # loaded for every test in every class
        sightings.json
    TestApp/
        common/                # loaded for all TestApp tests
            reports.json
        test_sightings_only/   # loaded only for that test
            sightings.json     # overrides common/sightings.json
        test_empty/
            sightings.json     # [] — overrides for empty-result test
```

Later directories replace earlier ones for the same filename — no merging.

---

## Profile, PipelineTask, PipelineExpected

Import from `tcex_testing.apps.tie.profile`:

```python
from tcex_testing.apps.tie.profile import (
    FetchRecord,
    PipelineExpected,
    PipelineTask,
    Profile,
    Record,
    UploadExpected,
)
from tcex_testing.checks import Check
from tcex_testing.profile import Stage
```

### `PipelineTask`

```python
class PipelineTask(BaseModel):
    task_cls: type
    stage: str                    # 'download' | 'convert' | 'upload' (or custom)
    expected: Expected = Expected()
    before: Callable | None = None   # called before stage runs, receives (harness,)
    after: Callable | None = None    # called after stage runs, receives (harness, result)
```

### `PipelineExpected`

Used for stages that write files (Download, Convert). Declares what data to
extract from the output and what checks to run against it.

```python
class Record(BaseModel):
    key: str       # label — referenced in checks via Check.on(key)
    file: str      # glob pattern relative to stage output_dir
    jmespath: str  # JMESPath expression applied to each matched file's content

class PipelineExpected(Expected):
    records: list[Record] = []
    checks: list[CheckLike] = []   # ScopedCheck | Callable
```

### `FetchRecord`

```python
class FetchRecord(BaseModel):
    key: str        # label — referenced in checks via Check.on(key)
    path: str       # TC v3 API path (e.g. 'indicators/addresses')
    params: dict = {}  # query params — typically 'tql' and 'fields'
```

### `UploadExpected`

```python
class UploadExpected(Expected):
    records: list[FetchRecord] = []
    checks: list[CheckLike] = []   # ScopedCheck | Callable
```

`records` — each `FetchRecord` queries the TC v3 API and stores the response
`data` list under `record.key`. Use broad TQL filters (e.g. by time window) to
assert everything the upload produced in one call.

`checks` — same scoped check system as `PipelineExpected`: `Check.on(key)`,
`Check.all()`, `Check.any()`, `Check.count()`, `Check.jmespath()`, or plain
callables receiving the full `resolved` dict.

### TIE `Profile`

```python
class Profile(BaseModel):
    job_request: Any              # app-specific JobRequestModel
    pipeline: list[PipelineTask]
    stage: Stage = Stage()        # shared Stage from tcex_testing.profile
```

---

## Scoped checks

`PipelineExpected.checks` accepts `ScopedCheck` instances (from `Check.on` /
`Check.all` / `Check.any` / `Check.count`) and plain callables for custom logic.

```python
checks=[
    # Specific record — by key
    Check.on('sightings').is_not_empty,          # singleton proxy
    Check.on('sightings').length_gt(0),          # factory proxy
    Check.on('sightings').deep_diff([...]),

    # All records — every resolved value must pass
    Check.all().is_not_empty,

    # Any record — at least one must pass
    Check.any().contains('malware'),

    # General — total item count across all records
    Check.count(min=5),

    # Custom callable — receives full resolved records dict
    lambda records: all('id' in item for item in records['sightings']),
]
```

---

## Tests

One comprehensive example showing all features wired together: vault-resolved
credentials, class-level TC staging, per-test staging via `Profile.stage`, env
override, mock SDK, scoped `Check` assertions on download output,
`UploadExpected` TC object assertions, and an `after=` hook for mid-pipeline
custom assertions.

```python
# tests/test_pipeline.py
import pytest
from tcex_testing.apps.tie.profile import (
    FetchRecord,
    PipelineExpected,
    PipelineTask,
    Profile,
    Record,
    UploadExpected,
)
from tcex_testing.checks import Check
from tcex_testing.profile import Stage, StagedItem
from task.download import Download
from task.convert import Convert
from task.upload import Upload
from tests.harness.base import AppTestCase


@pytest.mark.unit
class TestAppPipeline(AppTestCase):
    """Full pipeline test — mock SDK + vault credentials + TC staging + env override."""

    # ── Class-level TC staging ────────────────────────────────────────────────

    def stage(self) -> None:
        self.stager.stage(
            key='existing_ip',
            path='indicators/addresses',
            params={'summary': '192.0.2.1', 'rating': 1},
        )

    # ── Tests ─────────────────────────────────────────────────────────────────

    def test_full_pipeline(self):
        """
        Demonstrates all features in one test:
          - vault-resolved credentials (create_settings / create_sdk)
          - mock SDK loading fixture data
          - pre-staged TC indicator to verify the app enriches it (from stage())
          - env override for the duration of the pipeline
          - declarative PipelineExpected with scoped Check assertions on download output
          - UploadExpected asserting TC object state after upload
          - after= hook for custom mid-pipeline assertion
        """
        def after_download(harness, result):
            # Custom assertion between download and convert
            assert result.output_dir.exists(), 'Download wrote no output dir'

        self.run(Profile(
            job_request=self.create_job(hours_back=24, sample_types=['event', 'report']),
            pipeline=[
                PipelineTask(
                    task_cls=Download,
                    stage='download',
                    expected=PipelineExpected(
                        records=[
                            Record(
                                key='sightings',
                                file='sightings_*.json.gz',
                                jmespath='$.data[*]',
                            ),
                            Record(
                                key='reports',
                                file='reports_*.json.gz',
                                jmespath='$.data[*]',
                            ),
                        ],
                        checks=[
                            Check.on('sightings').is_not_empty,
                            Check.on('reports').is_not_empty,
                            Check.all().is_not_empty,          # every extracted list is non-empty
                            Check.count(min=2),                 # at least 2 items total
                            # custom: every sighting has an 'id' field
                            lambda records: all('id' in s for s in records['sightings']),
                        ],
                    ),
                    after=after_download,
                ),
                PipelineTask(task_cls=Convert, stage='convert'),
                PipelineTask(
                    task_cls=Upload,
                    stage='upload',
                    expected=UploadExpected(
                        records=[
                            FetchRecord(
                                key='uploaded_ips',
                                path='indicators/addresses',
                                params={
                                    'tql': 'dateAdded > "1 hour ago" AND ownerName = "TCI"',
                                    'fields': ['type', 'summary', 'rating', 'confidence'],
                                },
                            ),
                        ],
                        checks=[
                            Check.on('uploaded_ips').jmespath('[*].type', Check.all_match('Address')),
                            Check.on('uploaded_ips').jmespath('[*].rating', Check.all_match(Check.gte(3))),
                            Check.on('uploaded_ips').jmespath('[*].confidence', Check.all_match(Check.between(50, 100))),
                            Check.count(min=1),
                            # custom: verify the specific pre-staged IP was enriched
                            lambda records: any(
                                r['summary'] == '192.0.2.1' for r in records['uploaded_ips']
                            ),
                        ],
                    ),
                ),
            ],
            stage=Stage(
                env={'APP_FEED_MODE': 'full'},
                threatconnect=[
                    StagedItem(key='related_group', path='groups/reports', params={'name': 'Baseline Report'}),
                ],
            ),
        ))
```

---

## Running tests

```bash
# unit tests — fixture SDK, no credentials
pytest tests/test_pipeline.py -m unit -v

# integration — real vendor SDK
VENDOR_API_KEY='...' pytest tests/test_pipeline.py -m integration -k 'Integration' -v

# full E2E — real vendor + TC
VENDOR_API_KEY='...' TC_API_PATH='...' TC_API_ACCESS_ID='...' TC_API_SECRET_KEY='...' \
  pytest tests/test_pipeline.py -m integration -k 'LiveUpload' -v
```
