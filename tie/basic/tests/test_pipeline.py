"""Worked example — pipeline tests for this app. Adapt, do not run as-is.

The two classes below show the two shapes a TIE test takes:

  TestDownload  — unit. Fixture-backed SDK, no credentials, no network. This is
                  where most tests belong; they run anywhere, including CI.
  TestPipeline  — integration. Real Convert + Upload against a live TC instance.
                  Needs TC_API_* credentials and is marked so it can be excluded.

Both describe a run declaratively with a `Profile`: which tasks run in order,
what output files they should produce, and what must be true of the contents.
The harness executes it and does the asserting.

Fixtures for a test live in tests/fixtures/<ClassName>/<test_name>/ and are
matched by filename stem — `events.json` becomes `self._data['events']` in
MockSDK. Files in tests/fixtures/common/ apply to every test.

Unlike tests/tcex_testing/, this file is yours: template updates will not
overwrite it once you have edited it.
"""

import os

import pytest
import requests

from tcex_testing.apps.tie.profile import (
    PipelineExpected,
    PipelineTask,
    Profile,
    Record,
    UploadExpected,
)
from tcex_testing.checks import Check

from harness.base import AppTestCase  # type: ignore[import-not-found]

# TODO: point these at this app's tasks — ingest or egress.
from task.ingest.convert import Convert  # noqa: E402
from task.ingest.download import Download  # noqa: E402
from task.ingest.upload import Upload  # noqa: E402


@pytest.mark.unit
class TestDownload(AppTestCase):
    """Download-only tests. Fixture-backed, no TC credentials required."""

    use_mock = True

    def test_download_writes_events(self):
        """Download turns fixture records into gzipped output files.

        `Record` maps a glob over the task's output dir to a key, applying a
        jmespath expression to each matched file's contents. `Check.on(key)`
        then asserts against what that key resolved to.

        The three records asserted here come from tests/fixtures/common/events.json,
        which MockSDK.events() returns in place of a live API call.
        """
        self.run(Profile(
            job_request=self.create_job(hours_back=2),
            pipeline=[
                PipelineTask(
                    task_cls=Download,
                    expected=PipelineExpected(
                        records=[
                            Record(key='events', file='*event*.json.gz', jmespath='[*]'),
                        ],
                        checks=[
                            Check.on('events').is_not_empty(),
                            Check.on('events').length(3),
                            Check.on('events').jmespath('[0].id', 'evt-1001'),
                            Check.on('events').jmespath('[0].name', 'Sample Event One'),
                        ],
                    ),
                ),
            ],
        ))

    def test_download_handles_empty_response(self):
        """No fixture data means no records — and no crash.

        This is the fixture override mechanism in action:
        tests/fixtures/TestDownload/test_download_handles_empty_response/events.json
        holds `[]`, which replaces the three records in fixtures/common/ for this
        test only. Pins the empty-feed path, which is easy to break and never
        exercised by the happy-path test above.
        """
        self.run(Profile(
            job_request=self.create_job(hours_back=2),
            pipeline=[
                PipelineTask(
                    task_cls=Download,
                    expected=PipelineExpected(
                        records=[
                            Record(key='events', file='*event*.json.gz', jmespath='[*]'),
                        ],
                        checks=[Check.on('events').length(0)],
                    ),
                ),
            ],
        ))

    def test_download_surfaces_sdk_errors(self):
        """An SDK error propagates instead of being swallowed into an empty feed.

        `sdk_error` (defined on AppTestCase) patches an SDK method to raise on
        its first N calls, then delegate to the real implementation.

        This template's Download calls `self.sdk.events(...)` in a bare loop with
        no retry, so a single failure surfaces — and that is the behaviour worth
        pinning, because the alternative (a swallowed error producing zero
        records) looks identical to a genuinely empty feed.

        Once you add retry/backoff to Download, invert this: set `fail_count`
        below the retry limit and assert the records still arrive.
        """
        with pytest.raises(requests.HTTPError):
            self.run(Profile(
                job_request=self.create_job(hours_back=2),
                pipeline=[
                    PipelineTask(
                        task_cls=Download,
                        before=self.sdk_error('events', fail_count=1, status=429),
                        expected=PipelineExpected(
                            records=[
                                Record(key='events', file='*event*.json.gz', jmespath='[*]'),
                            ],
                            checks=[Check.on('events').is_not_empty()],
                        ),
                    ),
                ],
            ))


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get('TC_API_ACCESS_ID'),
    reason='integration test requires TC credentials (TC_API_*)',
)
class TestPipeline(AppTestCase):
    """Full Download -> Convert -> Upload against a live TC instance.

    Requires TC_API_PATH, TC_API_ACCESS_ID, TC_API_SECRET_KEY, and TC_OWNER.
    The skipif above means a fresh scaffold reports a clean skip instead of an
    Upload failure that looks like a broken template.

    Without credentials the harness also falls back to a no-op stager, so any
    attempt to stage TC objects raises with a clear message rather than a
    KeyError.

    Objects created here are tagged with the per-test TCEX_RUN_TAG and removed
    by AppTestCase._cleanup afterwards.
    """

    use_mock = True  # fixture download, real convert + upload

    def test_full_pipeline(self):
        """Fixture data survives the whole pipeline and lands in TC."""
        self.run(Profile(
            job_request=self.create_job(hours_back=2),
            pipeline=[
                PipelineTask(
                    task_cls=Download,
                    expected=PipelineExpected(
                        records=[
                            Record(key='events', file='*event*.json.gz', jmespath='[*]'),
                        ],
                        checks=[Check.on('events').is_not_empty()],
                    ),
                ),
                PipelineTask(
                    task_cls=Convert,
                    # Convert skips any sample type not enabled in settings, and
                    # silently — an empty output dir, not an error. Enabling it
                    # here rather than in create_settings() keeps the harness
                    # default matching production, where the list starts empty.
                    before=lambda h: h.set_app_settings(sample_types=['event']),
                    expected=PipelineExpected(
                        records=[
                            # Convert writes with page_name='event' too, so the
                            # glob matches the download stage's — but each stage
                            # gets its own output dir, so they never collide.
                            # write_batch emits {group, indicator, association},
                            # hence 'group[*]' rather than a bare '[*]'.
                            Record(key='groups', file='*event*.json.gz', jmespath='group[*]'),
                        ],
                        checks=[
                            Check.on('groups').is_not_empty(),
                            # sample_transform.json maps name -> name, id -> xid.
                            Check.on('groups').jmespath('[0].name', 'Sample Event One'),
                        ],
                    ),
                ),
                PipelineTask(
                    task_cls=Upload,
                    # UploadExpected queries TC after the upload rather than
                    # reading output files — this is the assertion that proves
                    # data actually reached the platform.
                    expected=UploadExpected(
                        checks=[
                            # TODO: assert on what this app uploads, e.g.
                            # Check.on('groups').is_not_empty(),
                        ],
                    ),
                ),
            ],
        ))
