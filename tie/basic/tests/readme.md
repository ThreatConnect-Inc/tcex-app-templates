# Tests

This app uses the `tcex_testing` framework, vendored at `tests/tcex_testing/`.

Tests are written declaratively: a `Profile` names the pipeline tasks to run, the
output files each should produce, and the assertions to make against them. The
harness runs the pipeline and does the checking.

## Layout

```
tests/
├── conftest.py          # sys.path setup only — no fixtures
├── harness/
│   ├── base.py          # AppTestCase — YOUR app wiring. Start here.
│   └── mock_sdk.py      # MockSDK — fixture-backed vendor SDK
├── fixtures/            # JSON fixture data (see below)
├── test_pipeline.py     # worked example — adapt it
└── tcex_testing/        # the framework. Do not edit — see "Updating".
```

## Getting started

1. Fill in `harness/base.py`. Every `create_*` method is abstract and app-specific:
   inputs, settings, DB, SDK, and job request. `run_pipeline_task()` needs to match
   your task constructors.
2. Fill in `harness/mock_sdk.py`, overriding only the SDK methods that reach the
   vendor API. Everything else keeps running for real.
3. Adapt `test_pipeline.py` and drop fixture JSON into `tests/fixtures/`.

## Fixtures

Resolved per test, later overriding earlier for the same filename stem:

1. `tests/fixtures/common/`
2. `tests/fixtures/<TestClassName>/common/`
3. `tests/fixtures/<TestClassName>/<test_name>/`

A file `events.json` becomes `self._data['events']` inside `MockSDK`. Override is
whole-file, not a merge — the most specific `events.json` replaces the rest.

Two example fixtures ship with the template:

```
fixtures/common/events.json                                    3 sample records
fixtures/TestDownload/test_download_handles_empty_response/
    events.json                                                [] — overrides the above
```

That pair is what makes `test_download_writes_events` and
`test_download_handles_empty_response` pass out of the box while sharing one
MockSDK method. Replace the contents with your vendor's real response shape.

## Running

```bash
pytest tests/                      # everything
pytest tests/ -m unit              # fixture-backed only, no credentials
pytest tests/ -m integration       # requires live TC credentials
```

Unit tests need no credentials. Integration tests that stage or upload TC objects
need `TC_API_PATH`, `TC_API_ACCESS_ID`, `TC_API_SECRET_KEY`, and `TC_OWNER`. When
those are unset the harness substitutes a no-op stager, so unit runs work offline;
attempting to actually stage an object then fails with an explicit message rather
than a bare `KeyError`.

Set `TCEX_TESTING_NO_CLEANUP=1` to leave staged TC objects in place for inspection
after a run.

## Updating

`tests/tcex_testing/` is delivered and maintained by the app template. Do not edit
it — template updates overwrite files whose contents still match the template, so
local edits are either lost or silently block the update.

Everything outside `tcex_testing/` — `conftest.py`, `harness/`, `fixtures/`, and
your test modules — belongs to this app and is left alone by updates.

Found a framework bug? Fix it in `tcex-app-templates/tie/basic/tests/tcex_testing/`
and let it flow back down, so the fix reaches every app instead of one.
