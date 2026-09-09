"""ThreatConnect API Service App"""

from functools import cached_property

from core.api.injectable.middleware import InjectableMiddleware
from core.app.api_service_falcon_abc import ApiServiceFalconABC
from model.settings_model import AppSettings, SettingModel
from sdk.egress_sdk import EgressSDK
from sdk.sdk import SDK
from task.egress.convert import Convert as EgressConvert
from task.egress.download import Download as EgressDownload
from task.egress.scheduler import Scheduler as EgressScheduler
from task.egress.upload import Upload as EgressUpload
from task.ingest.convert import Convert as IngestConvert
from task.ingest.download import Download as IngestDownload
from task.ingest.scheduler import Scheduler as IngestScheduler
from task.ingest.upload import Upload as IngestUpload


class App(ApiServiceFalconABC):
    """API Service App"""

    def __init__(self, _tcex):
        """Initialize class properties."""
        super().__init__(_tcex)

    def initialize_app(self):
        """Initialize the app."""
        self.register_custom_tasks()
        self.register_custom_middleware()
        self.register_custom_routes()
        self.register_custom_preflight_checks()
        self.register_custom_migration_actions()

    # TODO: Should this follow the same pattern as the other methods?
    def register_custom_migration_actions(self):
        """Register migration actions."""
        return

    def register_custom_tasks(self):
        """Register tasks."""
        self.register_tasks(
            # pipeline param is optional and useful if there are multiple pipes using the same task
            pipes=[
                (
                    IngestDownload(
                        self.settings,
                        self.tcex,
                        self.db,
                        sdk=self.sdk,
                        pipeline='ingest',
                    ),  # SDK Is optional
                    IngestConvert(self.settings, self.tcex, self.db, pipeline='ingest'),
                    IngestUpload(self.settings, self.tcex, self.db, pipeline='ingest'),
                ),
                (
                    EgressDownload(self.settings, self.tcex, self.db, pipeline='egress'),
                    EgressConvert(self.settings, self.tcex, self.db, pipeline='egress'),
                    EgressUpload(
                        self.settings,
                        self.tcex,
                        self.db,
                        sdk=self.egress_sdk,
                        pipeline='egress',
                    ),  # SDK Is optional
                ),
            ],
            standalone=[
                IngestScheduler(self.settings, self.tcex, self.db, pipeline='ingest'),
                EgressScheduler(self.settings, self.tcex, self.db, pipeline='egress'),
                # BackfillMissingReport(self.custom_settings, self.tcex, self.db, self.sdk)
            ],
            default=[self.tasks.CLEANER],
        )

    def register_custom_middleware(self):
        """Register middleware."""
        self.register_middleware(
            [
                InjectableMiddleware(
                    db=self.db,
                    sdk=self.sdk,
                    settings=self.settings,
                    tasks=self.tasks_obj,
                    logger=self.log,
                )
            ],
            default=[
                self.middleware.TCEX,
                self.middleware.VALIDATION,
                self.middleware.ERROR,
            ],
        )

    def register_custom_routes(self):
        """Register routes."""
        self.register_routes(default=[self.routes.ALL_TIE])

    def register_custom_preflight_checks(self):
        """Register preflight checks."""
        self.register_preflight_checks(
            preflight_checks=[self._check_api],
            default=[
                self.preflight_checks.FILESYSTEM,
                self.preflight_checks.TC_API,
                self.preflight_checks.DUPLICATE_PROCESSES_RUNNING,
            ],
        )

    @property
    def sdk(self):
        """Return the SDK."""
        return SDK(self.tcex)

    @property
    def egress_sdk(self):
        """Return the SDK."""
        return EgressSDK()

    def _check_api(self):
        """Perform preflight check."""
        try:
            self.sdk.test_connection(self.settings)
            self.log.info('Successfully connected to API')
        except Exception as ex:
            self.log.exception('Failed to connect to API')
            msg = 'Failed to connect to API.'
            raise RuntimeError(msg) from ex

    @property
    def log_path(self):
        """Return the log path."""
        return self.model.tc_log_path

    @property
    def db_path(self):
        """Return the path JsonDB should use.

        Derived from the tcex inputs rather than from `settings` (the core default is
        `self.settings.base_path / 'json_db'`). `settings` now reads its persisted values
        out of the DB, and `db` is a `cached_property` with no recursion guard, so the
        core definition would recurse `settings -> db -> db_path -> settings`. The
        resolved path is identical — `settings` sets `base_path=self.model.tc_out_path`.
        """
        return self.model.tc_out_path / 'json_db'

    @cached_property
    def settings(self):
        """Return settings.

        The admin-editable settings come from the JSON DB via `AppSettings.load`, which
        seeds itself from the tcex inputs on first boot. Everything else here — paths,
        identity, the catalogue — is read from the inputs on every boot and never
        persisted.
        """
        return SettingModel(
            tc_owner=self.model.tc_owner,
            base_path=self.model.tc_out_path,
            all_sample_types=['Event', 'URL', 'File', 'Host'],
            app_settings=AppSettings.load(self.db, self.model),
            name='Sample API Service',
            description='Sample API Service',
        )
