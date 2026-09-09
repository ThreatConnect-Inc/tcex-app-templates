"""AppTestCase — the per-app test harness. THIS FILE IS A SKELETON: fill it in.

`TieTestCase` (in tests/tcex_testing/apps/tie/base.py) owns the generic TIE test
lifecycle. It cannot know this app's constructor signatures, settings fields, or
DI wiring, so it leaves those as abstract methods for this file to implement.

Every `create_*` method below is required. `run_pipeline_task` is technically
optional but in practice always needs overriding, because TIE task constructors
differ per app.

Once this file is filled in, a test class inherits it and describes runs
declaratively — see tests/test_pipeline.py.

Unlike tests/tcex_testing/, this file is yours: template updates will not
overwrite it once you have edited it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

from tcex_testing.apps.tie.base import TieTestCase
from tcex_testing.apps.tie.result import ConvertResult, DownloadResult, UploadResult


class AppTestCase(TieTestCase):
    """Base test case for this app. Subclass it in your test modules."""

    # True  -> create_mock_sdk() is used (fixture-backed, no vendor API calls).
    # False -> create_sdk() is used (real SDK; needs live credentials).
    use_mock: bool = True

    # -- Required: app wiring --------------------------------------------------

    def create_inputs(self) -> dict:
        """Inputs used to build the TcEx instance for each test.

        These stand in for the deploy-time App inputs. Add whatever this app's
        app_inputs.py declares as required.
        """
        return {
            'tc_owner': 'TCI',
            # TODO: add this app's connection inputs, e.g.
            # 'api_url': 'https://api.example.test',
            # 'api_key': 'test-api-key',
        }

    def create_settings(self):  # type: ignore[override]
        """Build the SettingModel each task under test receives.

        Imported inside the method, not at module scope: conftest.py must finish
        setting up sys.path before app modules are importable. Every app import
        in this file follows that rule.
        """
        from model.settings_model import AppSettings, SettingModel  # noqa: PLC0415

        return SettingModel(
            base_path=self._output_dir,
            name='Test App',
            description='Test settings',
            tc_owner='TCI',
            # TODO: match this app's SettingModel fields.
            api_url='https://api.example.test',
            api_key='test-api-key',
            app_settings=AppSettings(**self._app_settings_overrides),
        )

    def create_db(self):  # type: ignore[override]
        """Build a JsonDB rooted in this test's temp output dir."""
        from core.json_db import JsonDB  # noqa: PLC0415

        def _json_default(value):
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, timedelta):
                return value.total_seconds()
            return str(value)

        return JsonDB(self._output_dir, self.log, json_args={'default': _json_default})

    def create_sdk(self):  # type: ignore[override]
        """Build the real vendor SDK. Used when use_mock is False."""
        from sdk.sdk import SDK  # noqa: PLC0415

        return SDK(self.tcex)

    def create_mock_sdk(self):  # type: ignore[override]
        """Build the fixture-backed SDK. Used when use_mock is True."""
        from harness.mock_sdk import MockSDK  # type: ignore[import-not-found]  # noqa: PLC0415

        return MockSDK(self.tcex)

    def create_job_request(  # type: ignore[override]
        self,
        updated_since: datetime,
        updated_till: datetime,
        **kwargs,  # noqa: ARG002
    ):
        """Build the JobRequestModel a pipeline run operates on.

        Called by TieTestCase.create_job(hours_back=N), which supplies the time
        window. `status` and `date_queued` are required by JobRequestBaseModel;
        the rest come from this app's JobRequestModel.
        """
        from model.job_request_model import JobRequestModel  # noqa: PLC0415

        return JobRequestModel(
            status='pending',
            date_queued=datetime.now(UTC),
            start_time=updated_since,
            end_time=updated_till,
        )

    # -- Settings overrides ----------------------------------------------------

    @property
    def _app_settings_overrides(self) -> dict:
        """Fields to override on the AppSettings built by create_settings().

        run_pipeline_task() calls create_settings() fresh for every task, so there
        is no single long-lived settings object a before= hook could mutate. Use
        set_app_settings() instead.
        """
        return getattr(self, '_app_settings_overrides_value', {})

    def set_app_settings(self, **overrides) -> None:
        """Override AppSettings fields for every subsequent task in this test.

        Use from a before= hook, ahead of the PipelineTask it should affect::

            PipelineTask(
                task_cls=Download,
                before=lambda h: h.set_app_settings(sample_types=['event']),
            )
        """
        self._app_settings_overrides_value = overrides

    # -- Required: task runner -------------------------------------------------

    def run_pipeline_task(self, task_cls: type, prev_result: Any = None) -> Any:
        """Instantiate and run one pipeline task, returning its typed result.

        Override territory, because TIE task constructors vary per app. The
        pattern below is the common one:

          - Seed the DI container via beacon.provide() BEFORE constructing a
            task. TaskABC resolves settings/tcex/db/supervisor through inject()
            defaults, which raise InjectionError if nothing is registered.
          - Inject fakeredis before instantiation — TaskABC.namespace is a
            cached_property that reaches for the key-value store.
          - Call the task's own entry point directly (download(), run()) rather
            than run_pipe_task(), which needs the full job pipeline machinery
            (job_dao, metrics, probation checks).

        Returns DownloadResult / ConvertResult / UploadResult so the profile
        layer knows where to look for output.
        """
        import fakeredis  # type: ignore[import-not-found]  # noqa: PLC0415

        from core.beacon import provide  # noqa: PLC0415
        from core.supervisor import Supervisor  # noqa: PLC0415
        from core.task.task_path_pipe_injectables import CurrentJob  # noqa: PLC0415

        # TODO: point these at this app's tasks — ingest or egress.
        from task.ingest.convert import Convert  # noqa: PLC0415
        from task.ingest.download import Download  # noqa: PLC0415
        from task.ingest.upload import Upload  # noqa: PLC0415

        settings = self.create_settings()
        mock_supervisor = MagicMock(spec=Supervisor)

        provide(settings)
        provide(self.tcex)
        provide(self.db)
        provide(mock_supervisor)
        provide(self._job_request, type_=CurrentJob)

        object.__setattr__(
            self.tcex.app.key_value_store, 'redis_client', fakeredis.FakeRedis()
        )

        if task_cls is Download:
            output_dir = self._output_dir / 'download'
            output_dir.mkdir(parents=True, exist_ok=True)
            task = task_cls(settings=settings, tcex=self.tcex, db=self.db, sdk=self.sdk)
            task.download(output_dir, self._job_request)
            self.last_download = task
            return DownloadResult(output_dir=output_dir, job_request=self._job_request)

        if task_cls is Convert:
            assert isinstance(prev_result, DownloadResult)
            output_dir = self._output_dir / 'convert'
            output_dir.mkdir(parents=True, exist_ok=True)
            task = task_cls(settings=settings, tcex=self.tcex, db=self.db)
            task.run(self._job_request.request_id, prev_result.output_dir, output_dir)
            return ConvertResult(output_dir=output_dir, job_request=self._job_request)

        if task_cls is Upload:
            assert isinstance(prev_result, ConvertResult)
            output_dir = self._output_dir / 'upload'
            output_dir.mkdir(parents=True, exist_ok=True)
            task = task_cls(settings=settings, tcex=self.tcex, db=self.db)
            task.run(self._job_request.request_id, prev_result.output_dir, output_dir)
            return UploadResult(tcex=self.tcex)

        raise NotImplementedError(f'Unknown task class: {task_cls.__name__}')

    # -- Optional: fault injection ---------------------------------------------

    def sdk_error(self, method_name: str, *, fail_count: int = 1, status: int = 429):
        """Return a before= callable that fails the first N SDK calls, then succeeds.

        Use to exercise retry and backoff paths::

            PipelineTask(
                task_cls=Download,
                before=self.sdk_error('events', fail_count=2, status=401),
            )
        """
        if not hasattr(self.sdk, method_name):
            valid = [m for m in dir(self.sdk) if not m.startswith('_')]
            raise AttributeError(
                f'SDK has no method {method_name!r}. Valid methods: {valid}'
            )

        def before(harness):
            import requests  # noqa: PLC0415

            original = getattr(harness.sdk, method_name)
            counter = {'n': 0}
            mock_response = MagicMock()
            mock_response.status_code = status
            error = requests.HTTPError(response=mock_response)

            def patched(*args, **kwargs):
                counter['n'] += 1
                if counter['n'] <= fail_count:
                    raise error
                return original(*args, **kwargs)

            setattr(harness.sdk, method_name, patched)

        return before

    # -- Optional: cleanup -----------------------------------------------------

    def _cleanup(self, *_) -> None:
        """Delete TC objects this run created, matched by its unique run tag.

        Only relevant for integration tests that write to a live TC instance.
        TestCaseBase sets TCEX_RUN_TAG per test; tag your uploads with it so this
        can find them.
        """
        tql_tag = f'tag EQ "{self._run_tag}"'
        for item in self.fetch('groups', {'tql': tql_tag}):
            self.tcex.session.tc.delete(f'/v3/groups/{item["id"]}')
        for item in self.fetch('indicators', {'tql': tql_tag}):
            self.tcex.session.tc.delete(f'/v3/indicators/{item["id"]}')
