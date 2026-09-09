"""TIE (FeedApiService) test case base class.

Test classes inherit directly from TieTestCase — the class IS the harness.
No fixture parameters. Implement the six abstract methods on the test class.

Usage:
    class TestApp(TieTestCase):
        use_mock = True

        def create_inputs(self): ...
        def create_settings(self): ...
        def create_db(self): ...
        def create_mock_sdk(self): ...
        def create_sdk(self): ...
        def create_job_request(self, updated_since, updated_till, **kwargs): ...

        def run_pipeline_task(self, task_cls, prev_result=None):
            task = task_cls(settings=self.create_settings(), sdk=self.sdk)
            task.run(self._job_request)
            return DownloadResult(output_dir=self._output_dir,
                                  job_request=self._job_request)

        def test_download_sightings(self):
            self.run(Profile(
                job_request=self.create_job(hours_back=2, sample_types=['event']),
                pipeline=[
                    PipelineTask(
                        task_cls=Download,
                        expected=PipelineExpected(
                            records=[Record(key='sightings', file='*sighting*.json.gz', jmespath='[*]')],
                            checks=[Check.on('sightings').is_not_empty(), Check.count(min=1)],
                        ),
                    ),
                ],
            ))

        def test_full_pipeline(self):
            self.run(Profile(
                job_request=self.create_job(hours_back=2),
                pipeline=[
                    PipelineTask(task_cls=Download),
                    PipelineTask(task_cls=Convert),
                    PipelineTask(task_cls=Upload, expected=UploadExpected()),
                ],
            ))
"""
from __future__ import annotations

# standard library
import os
from abc import abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

# third-party
import pytest

from tcex_testing.apps.tie.profile import Profile, UploadExpected
from tcex_testing.apps.tie.result import UploadResult
from tcex_testing.harness import TestCaseBase
from tcex_testing.tc_stager import TcStager


class TieTestCase(TestCaseBase):
    """Base class for TIE FeedApiService app tests. Inherit directly in test files.

    app_dir is resolved automatically from the concrete test class file location.
    use_mock controls whether create_mock_sdk() or create_sdk() is called.
    """

    sdk: Any = None
    db: Any = None            # set in _setup_sdk() via create_db()
    _job_request: Any = None  # set by run() before _run_pipeline; accessible in run_pipeline_task

    # -- pytest per-test lifecycle --------------------------------------------

    def setup_method(self, method=None) -> None:
        self.sdk = None
        self.last_download = None
        self.last_convert = None
        self.last_upload = None
        super().setup_method(method)
        self._setup_sdk()

    def teardown_method(self, *_) -> None:
        self.teardown()
        super().teardown_method()

    def teardown(self) -> None:
        """No-op by default. Override for app-specific cleanup."""

    def _setup_sdk(self) -> None:
        inputs = self.resolver.resolve(self.create_inputs())
        self._setup_tcex(inputs)
        self._setup_logging()
        self.db = self.create_db()

        if self.use_mock:
            self.sdk = self.create_mock_sdk()
            self.sdk._load_fixtures(self.fixture_paths)
        else:
            self.sdk = self.create_sdk()

    # -- Abstract interface ----------------------------------------------------

    @abstractmethod
    def create_inputs(self) -> dict:
        """Return all app input params for one test run.

        May contain ${env:NAME} or ${vault:path} refs — resolved automatically
        before TcEx is created.
        """

    @abstractmethod
    def create_settings(self):
        """Return the vendor SettingModel for this app.

            def create_settings(self):
                token = resolve_refs('${env:VENDOR_API_KEY}')
                return SettingModel(bearer_token=token, tc_owner=self.tc_owner)
        """

    @abstractmethod
    def create_db(self):
        """Return a DB instance (e.g. JsonDB) for the test run.

        Called once per test from _setup_sdk(). The result is stored as self.db
        and is available to run_pipeline_task and TieTestCase.run() (db.save()).

            def create_db(self):
                from core.json_db import JsonDB
                return JsonDB(self._output_dir, self.log)
        """

    @abstractmethod
    def create_sdk(self):
        """Return a real vendor SDK instance using live credentials."""

    @abstractmethod
    def create_mock_sdk(self):
        """Return a fixture-backed MockSDK instance."""

    @abstractmethod
    def create_job_request(self, updated_since: datetime, updated_till: datetime, **kwargs):
        """Return a JobRequestModel covering the given time window."""

    # -- Convenience job builder -----------------------------------------------

    def create_job(self, hours_back: int = 2, **kwargs):
        """Build a job request covering the last N hours from now."""
        now = datetime.now(tz=timezone.utc)
        since = now - timedelta(hours=hours_back)
        return self.create_job_request(updated_since=since, updated_till=now, **kwargs)

    # -- Pipeline task runner --------------------------------------------------

    def run_pipeline_task(self, task_cls: type, prev_result: Any = None) -> Any:
        """Run a single pipeline task and return its result.

        Override in AppTestCase to match the app's task constructor signature and
        DI requirements. self._job_request is set from Profile.job_request before
        this is called. prev_result is the result of the previous task (None for
        the first task in the pipeline).

        Example:
            def run_pipeline_task(self, task_cls, prev_result=None):
                task = task_cls(settings=self.create_settings(), sdk=self.sdk)
                task.run(self._job_request)
                return DownloadResult(output_dir=self._output_dir,
                                      job_request=self._job_request)
        """
        raise NotImplementedError(
            f'Override run_pipeline_task in {type(self).__name__} to instantiate '
            f'{task_cls.__name__} with the correct constructor signature.'
        )

    # -- Full-pipeline runner --------------------------------------------------

    def run(self, profile: Profile) -> None:
        """Run the full pipeline from a Profile; assert each stage's expected.

        Applies profile.stage.env overrides for the duration of the pipeline.
        Stages TC objects from profile.stage.threatconnect before the run and
        cleans them up after.
        """
        if profile.environments:
            active = set(os.environ.get('TCEX_TEST_ENVS', '').split(','))
            if not (set(profile.environments) & active):
                pytest.skip(f'environments {profile.environments!r} not in TCEX_TEST_ENVS={active!r}')

        stager = None
        if profile.stage.threatconnect:
            stager = TcStager()
            try:
                for item in profile.stage.threatconnect:
                    stager.stage(key=item.key, path=item.path, body=item.body, params=item.params)
            except Exception:
                stager.cleanup()
                raise

        self._job_request = profile.job_request
        self.db.save(profile.job_request)  # type: ignore[attr-defined]

        try:
            with patch.dict(os.environ, profile.stage.env):
                self._run_pipeline(profile)
        finally:
            if stager is not None:
                try:
                    stager.cleanup()
                except Exception:
                    pass

    def _run_pipeline(self, profile: Profile) -> None:
        """Execute each PipelineTask in order, feeding each result into the next."""
        _last_result: Any = None

        for task in profile.pipeline:
            befores = task.before if isinstance(task.before, list) else [task.before]
            for before in befores:
                before(self)

            result = self.run_pipeline_task(task.task_cls, _last_result)
            assert result is not None, f'run_pipeline_task returned None for {task.task_cls.__name__}'

            if isinstance(task.expected, UploadExpected):
                assert isinstance(result, UploadResult)
                result.assert_no_errors()

            resolved = task.expected.fetch_records(result)
            task.expected.assert_result(result, resolved)

            _last_result = result

            afters = task.after if isinstance(task.after, list) else [task.after]
            for after in afters:
                after(self, result)


# PipelineTask.before/after are typed as Callable[[TieTestCase], None]. Because
# TieTestCase is only imported under TYPE_CHECKING in profile.py, pydantic v1
# stores it as an unresolved ForwardRef at model-definition time and raises
# ConfigError: field "after" not yet prepared if update_forward_refs is never called.
# Importing PipelineTask here (after TieTestCase is fully defined) and calling
# update_forward_refs resolves the ref without creating a circular import.
from tcex_testing.apps.tie.profile import PipelineTask  # noqa: E402, PLC0415

PipelineTask.update_forward_refs(TieTestCase=TieTestCase)
