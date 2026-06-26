"""ThreatConnect API Service App"""

from datetime import timedelta
from functools import cached_property

from api.endpoint.enrichment_response import EnrichmentResponse
from core.api.endpoint.tcva.discovery_response import DiscoveryResponse
from core.api.injectable.middleware import InjectableMiddleware
from core.app.api_service_falcon_abc import ApiServiceFalconABC
from core.message_service.message_handler.discovery_handler import DiscoveryHandler
from core.model.scheduled_action_model import ScheduledActionModel
from core.model.settings_model_base import MessageBrokerSettings
from message_service.message_handler.enrichment_handler import EnrichmentHandler
from model.settings_model import SettingModel
from scheduled_action.actions import log_running_tasks
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
        self.register_custom_message_handlers()
        self.register_custom_scheduled_actions()
        self.register_custom_migration_actions()

    # TODO: Should this follow the same pattern as the other methods?
    def register_custom_migration_actions(self):
        """Register migration actions."""
        return

    def register_custom_scheduled_actions(self):
        """Register scheduled actions."""
        self.register_scheduled_actions(
            scheduled_actions=[
                ScheduledActionModel(
                    name='Log Currently Running Tasks',
                    interval=timedelta(minutes=5),
                    fn=log_running_tasks,
                    kwargs={'db': self.db, 'settings': self.settings, 'log': self.log},
                )
            ],
        )

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
        self.register_routes(
            {
                '/api/discovery': DiscoveryResponse(self.discovery_handler),
                '/api/enrich': EnrichmentResponse(self.enrichment_handler),
            },
            default=[self.routes.ALL_TIE],
        )

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

    @cached_property
    def discovery_handler(self):
        """Return the discovery handler."""
        return DiscoveryHandler(self.message_service, self.settings)

    @cached_property
    def enrichment_handler(self):
        """Return the enrichment handler."""
        return EnrichmentHandler(self.message_service, self.settings, self.sdk)

    def register_custom_message_handlers(self):
        """Register a message handler."""
        self.register_message_handlers(
            handlers={
                'service-discovery': self.discovery_handler,
                'ipv4-enrichment': self.enrichment_handler,
                'ipv6-enrichment': self.enrichment_handler,
                'host-enrichment': self.enrichment_handler,
                'md5-enrichment': self.enrichment_handler,
                'sha1-enrichment': self.enrichment_handler,
                'sha256-enrichment': self.enrichment_handler,
                'url-enrichment': self.enrichment_handler,
            }
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
    def message_broker_settings(self) -> MessageBrokerSettings:
        """Return the message broker settings."""
        return MessageBrokerSettings(
            schema_version='1.0.0',
            # TODO: Revisit this
            # provider_id=self.model.tc_session_id,
            provider_id='1',
            topic='indicator-enrichment-service',
            features={
                'service-discovery',
                'ipv4-enrichment',
                'ipv6-enrichment',
                'host-enrichment',
                'md5-enrichment',
                'sha1-enrichment',
                'sha256-enrichment',
                'url-enrichment',
            },
        )

    @property
    def log_path(self):
        """Return the log path."""
        return self.model.tc_log_path

    @cached_property
    def settings(self):
        """Return settings"""
        return SettingModel(
            tc_owner=self.model.tc_owner,
            base_path=self.model.tc_out_path,
            advanced_settings=self.model.advanced_settings,
            all_sample_types=['Event', 'URL', 'File', 'Host'],
            sample_types=self.model.sample_types,
            notification_digest_interval=self.model.notification_digest_interval,
            notification_types=self.model.notification_types,
            mb=self.message_broker_settings,
            name='Sample API Service',
            description='Sample API Service',
        )
