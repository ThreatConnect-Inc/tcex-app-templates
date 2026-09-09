"""ThreatConnect API Service Falcon API"""

import logging
from enum import Enum
from typing import Any

from core.api.endpoint.tc_app_config import TcAppConfig
from core.api.endpoint.tcvf.batch_error_collection import BatchErrorCollection
from core.api.endpoint.tcvf.batch_error_counts_collection import (
    BatchErrorCountsCollection,
)
from core.api.endpoint.tcvf.batch_error_export_resource import BatchErrorExportResource
from core.api.endpoint.tcvf.docs_resource import DocsResource
from core.api.endpoint.tcvf.download_files_resource import DownloadFilesResource
from core.api.endpoint.tcvf.health_resource import HealthResource
from core.api.endpoint.tcvf.job_file_download import JobFileDownload
from core.api.endpoint.tcvf.job_files import JobFiles
from core.api.endpoint.tcvf.job_retry_resource import JobRetryResource
from core.api.endpoint.tcvf.metric_processing_collection import (
    MetricProcessingCollection,
)
from core.api.endpoint.tcvf.metric_task_resource import MetricTaskResource
from core.api.endpoint.tcvf.notification_collection import NotificationCollection
from core.api.endpoint.tcvf.onboarding_resource import OnboardingResource
from core.api.endpoint.tcvf.report_pdf_tracker_collection import (
    ReportPDFTrackerCollection,
)
from core.api.endpoint.tcvf.request_collection import RequestCollectionResource
from core.api.endpoint.tcvf.settings_resource import (
    SettingsResource,
    SettingsRevisionsResource,
)
from core.api.endpoint.tcvf.settings_validate_resource import SettingsValidateResourceBase
from core.api.endpoint.tcvf.supervisor_resource import SupervisorResource
from core.api.endpoint.tcvf.support_log_search_resource import SupportLogSearchResource
from core.api.endpoint.tcvf.task_collection import TaskCollection
from core.api.endpoint.tcvf.task_item import TaskItem
from core.api.endpoint.tcvf.task_status_collection import TaskStatusCollection
from core.api.error.middleware import ErrorMiddleware
from core.api.tcex.middleware import TcExMiddleware
from core.api.validation.middleware import ValidationMiddleware
from core.task.cleaner import Cleaner
from core.task.metric_reporter import MetricReporter

# Unlike the others, this one falls back to a WORKING base rather than to None: an app
# with no checks of its own still gets a validate endpoint, it just reports nothing. An
# app that declares `validations()` has its subclass picked up here with no registration.
try:
    from api.endpoint.settings_validate_resource import SettingsValidateResource
except ImportError:
    SettingsValidateResource = SettingsValidateResourceBase

try:
    from api.endpoint.adhoc_job_request_resource import AdHocRequestResource
except ImportError:
    AdHocRequestResource = None

try:
    from api.endpoint.download_ti_resource import DownloadTiResource
except ImportError:
    DownloadTiResource = None

try:
    from core.api.endpoint.tcve.batch_error_collection import (
        BatchErrorCollection as TcveBatchErrorCollection,
    )
except ImportError:
    TcveBatchErrorCollection = None

try:
    from core.api.endpoint.tcve.config_resource import ConfigResource
except ImportError:
    ConfigResource = None

try:
    from core.api.endpoint.tcve.job_request_collection import JobRequestCollection
except ImportError:
    JobRequestCollection = None

try:
    from core.api.endpoint.tcve.task_collection import TaskCollection as TcveTaskCollection
except ImportError:
    TcveTaskCollection = None

try:
    from core.api.endpoint.tcve.task_status_collection import (
        TaskStatusCollection as TcveTaskStatusCollection,
    )
except ImportError:
    TcveTaskStatusCollection = None

try:
    from core.api.endpoint.tcve.test_config_resource import TestConfigResource
except ImportError:
    TestConfigResource = None

logger = logging.getLogger('tcex')


class BaseResource:
    """Base class for resources with optional initialization arguments."""

    def __init__(self, resource: type[object] | None, init_args: tuple[Any, ...] = ()):
        """Initialize the resource with optional initialization arguments."""
        self.resource = resource
        self.init_args = init_args
        self.log = logger

    def get_resource(self, instance: object = None) -> object | None:
        """Return the resource instance with resolved arguments."""
        if self.init_args and instance is None:
            msg = (
                f'Cannot initialize {self.resource.__name__} without instance '
                f'to resolve arguments: {self.init_args}'
            )
            raise ValueError(msg)
        if instance is None or self.resource is None:
            return None

        resolved_args = [getattr(instance, arg) for arg in self.init_args] if instance else []
        return self.resource(*resolved_args)


class Task(BaseResource):
    """Represents an API route with its corresponding resource class and optional init args."""


class TASKS(Enum):
    """Enum for task types."""

    CLEANER = Task(Cleaner, init_args=('settings', 'tcex', 'db', 'tasks_obj'))
    METRIC_REPORTER = Task(MetricReporter, init_args=('settings', 'tcex', 'db'))


class Middleware(BaseResource):
    """Represents an API route with its corresponding resource class and optional init args."""


class MIDDLEWARE(Enum):
    """Enum for middleware types."""

    # INJECTABLE =
    ERROR = Middleware(ErrorMiddleware)
    TCEX = Middleware(TcExMiddleware, init_args=('model', 'tcex'))
    VALIDATION = Middleware(ValidationMiddleware)


class PREFLIGHT_CHECKS(Enum):  # noqa: N801
    """Enum for middleware types."""

    FILESYSTEM = 'filesystem'
    TC_API = 'tc_api'
    DUPLICATE_PROCESSES_RUNNING = 'duplicate_processes_running'
    ATTRIBUTES = 'attributes'


class Route(BaseResource):
    """Represents an API route with its corresponding resource class and optional init args."""

    def __init__(self, path: str, resource: type[object] | None, init_args: tuple[Any, ...] = ()):
        """Initialize the route with its path, resource class, and optional init args."""
        super().__init__(resource, init_args)
        self.path = path


class ROUTES(Enum):
    """Enum grouping all route categories."""

    class TIE(Enum):
        """All TIE-related routes (ingress/ingest apps)."""

        JOB_FILES = Route('/api/job/{job_id}/files', JobFiles)
        JOB_FILE_DOWNLOAD = Route('/api/job/{job_id}/download', JobFileDownload)
        REQUEST_COLLECTION = Route('/api/job/request', RequestCollectionResource)
        REQUEST_RETRY = Route('/api/job/{job_id}/retry', JobRetryResource)
        TASK_STATUS_COLLECTION = Route('/api/task/status', TaskStatusCollection)
        TASK_COLLECTION = Route('/api/task', TaskCollection)
        TASK_ITEM = Route('/api/task/{task_name}', TaskItem)
        BATCH_ERROR_COUNTS_COLLECTION = Route(
            '/api/report/batch-error-counts', BatchErrorCountsCollection
        )
        BATCH_ERROR_COLLECTION = Route('/api/report/batch-error', BatchErrorCollection)
        BATCH_ERROR_EXPORT = Route('/api/report/batch-error/export', BatchErrorExportResource)
        METRIC_PROCESSING_COLLECTION = Route('/api/metric/processing', MetricProcessingCollection)
        METRIC_TASK_RESOURCE = Route('/api/metric/task', MetricTaskResource)
        SUPPORT_LOG_SEARCH_RESOURCE = Route('/api/support/log-search', SupportLogSearchResource)
        SUPERVISOR_RESOURCE = Route('/api/support/supervisor', SupervisorResource)
        HEALTH = Route('/api/health', HealthResource)
        NOTIFICATION_COLLECTION = Route('/api/notification', NotificationCollection)
        REPORT_PDF_TRACKER_COLLECTION = Route('/api/report/pdf-tracker', ReportPDFTrackerCollection)

        # Example: Route that requires additional arguments during initialization
        DOWNLOAD_DB_RESOURCE = Route(
            path='/api/db/download',
            resource=DownloadFilesResource,
            init_args=('db_path',),
        )
        APP_CONFIG = Route('/api/tc/app-config', TcAppConfig)

        # Every app gets these unchanged. `SettingsValidateResource` is the app's own
        # subclass when it has one and the core base otherwise — resolved by the optional
        # import above, so an app wires up its checks by declaring `validations()` and
        # nothing else.
        SETTINGS = Route('/api/settings', SettingsResource)
        SETTINGS_REVISIONS = Route('/api/settings/revisions', SettingsRevisionsResource)
        SETTINGS_VALIDATE = Route('/api/settings/validate', SettingsValidateResource)
        ONBOARDING = Route('/api/onboarding', OnboardingResource)
        DOCS = Route('/api/docs', DocsResource)

        AD_HOC_JOB_REQUEST_RESOURCE = Route('/api/job/adhoc', AdHocRequestResource)
        DOWNLOAD_TI = Route('/api/download/ti', DownloadTiResource)
        DOWNLOAD_LOGS = Route(
            '/api/logs/download',
            resource=DownloadFilesResource,
            init_args=('log_path',),
        )

    class TCVE(Enum):
        """All TCVE-related routes (egress apps).

        The resources are optional imports (see the try/except block above): they depend
        on app-side modules that only exist in a TCVE app (`model.tql_config_model`,
        `model.pipe_error_model`, `records.tql_config_record`, `records.pipe_error_record`).
        In any other app the import fails, the resource is None, `get_resource()` returns
        None, and the route is simply absent from the supported-route map.
        """

        CONFIG = Route('/api/tql-config', ConfigResource)
        TEST_CONFIG = Route('/api/tql-config/test', TestConfigResource)
        JOB_REQUEST = Route('/api/job/request', JobRequestCollection)
        TASK_STATUS = Route('/api/task/status', TcveTaskStatusCollection)
        TASK = Route('/api/task', TcveTaskCollection)
        TASK_ITEM = Route('/api/task/{task_name}', TcveTaskCollection)
        BATCH_ERROR = Route('/api/report/batch-error', TcveBatchErrorCollection)
        # Not a tcve-local resource -- this is the tcvf collection, already imported above.
        NOTIFICATION = Route('/api/notification', NotificationCollection)

    ALL_TIE = TIE
    ALL_TCVE = TCVE


# Back-compat alias for apps that import the sentinel directly; `ROUTES.ALL_TCVE` is
# the same member.
ALL_TCVE = ROUTES.ALL_TCVE
