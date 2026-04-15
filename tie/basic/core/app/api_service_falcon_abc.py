"""ThreatConnect API Service Falcon API"""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from functools import cached_property
from time import sleep, time
from typing import cast

import schedule
from tcex.api.tc.v3.tql.tql_operator import TqlOperator
from tcex.exit import ExitCode
from tcex.logger.trace_logger import TraceLogger

from app_inputs import AppBaseModel
from core.api.falcon_app import FalconApp
from core.api.spec import spec
from core.app.api_service_app_abc import ApiServiceAppABC
from core.app.enums import MESSAGE_HANDLERS, MIDDLEWARE, PREFLIGHT_CHECKS, ROUTES, TASKS
from core.beacon import provide
from core.json_db import JsonDB
from core.message_service.message_service import MessageService
from core.model.scheduled_action_model import ScheduledActionModel
from core.model.tie.job_request_base_model import JobRequestBaseModel
from core.service.preflight_check_service import PreflightCheckService
from core.supervisor import Supervisor
from core.task.tasks import Tasks
from core.util.custom_handler import CustomHandler
from model.settings_model import SettingModel

try:
    from migrations import Migrations
except ImportError:
    Migrations = None

logger: TraceLogger = cast('TraceLogger', logging.getLogger('tcex'))


class ApiServiceFalconABC(ApiServiceAppABC, ABC):
    """ThreatConnect API Service Falcon API"""

    def __init__(self, *args, **kwargs):
        """Initialize class properties."""
        super().__init__(*args, **kwargs)
        self._routes = {}
        self._preflight_checks = []
        self._tasks = {'pipe': [], 'standalone': []}
        self._middleware = []
        self._message_handlers = {}
        self._jobs = {}
        self.log = logger
        self.model: AppBaseModel = self.inputs.model  # type: ignore
        self.preflight_check_service = PreflightCheckService(self.tcex)
        self.migrations = Migrations(self.tcex, self.db, self.settings) if Migrations else None
        self.tasks_obj = Tasks(self.tcex, db=self.db, settings=self.settings)

        # properties
        self.app = FalconApp(sink_before_static_route=True)

        # provide dependencies
        provide(self.db)
        provide(self.tasks_obj.supervisor, type_=Supervisor)

        if (
            self.app.ui_files
            and self.app.ui_files.parent.is_dir()
            and not self.app.ui_files.exists()
        ):
            self.tcex.exit.exit(1, 'UI files not found. Ensure they are built.')

    def register_routes(self, routes: dict | None = None, default: list[ROUTES] | None = None):
        """Register all routes, optionally including default TIE routes."""
        # Handle special "ALL_" cases (e.g., ROUTES.ALL_TIE)
        routes = routes or {}
        default = default or []
        for route in default[:]:  # Copy the list to avoid modifying while iterating
            if route == ROUTES.ALL_TIE:
                self._routes.update(self.all_supported_routes.get('tie', {}))
                default.remove(route)  # Remove it from further processing

        # Loop through all supported route categories and register only matching ones
        for supported_routes in self.all_supported_routes.values():
            for route in default:
                if route in supported_routes:
                    self._routes[route] = supported_routes[route]

        self._routes.update(routes)

        for route, resource in self._routes.items():
            if resource:
                self.app.add_route(route, resource)
        self.spec.register(self.app)

    def register_preflight_checks(
        self,
        preflight_checks: list | None = None,
        default: list[PREFLIGHT_CHECKS] | None = None,
    ):
        """Register all preflight checks."""
        preflight_checks = preflight_checks or []
        default = default or []

        preflight_check_service = PreflightCheckService(self.tcex)
        for check in default[:]:
            check = preflight_check_service.mapping.get(check)
            self.preflight_check_service.register_preflight_check(check)

        self.preflight_check_service.preflight_checks.update(preflight_checks)

    def register_tasks(
        self,
        standalone: list | None = None,
        pipes: list | None = None,
        default: list[TASKS] | None = None,
    ):
        """Register tasks."""
        standalone = standalone or []
        pipes = pipes or []
        default = default or []

        for task in default[:]:
            self._tasks['standalone'].append(self.all_supported_tasks.get(task))

        self._tasks['standalone'].extend(standalone)
        self._tasks['pipe'].extend(pipes)
        for task in self._tasks['standalone']:
            if task:
                self.tasks_obj.add_task(task)

        for task in self._tasks['pipe']:
            if task:
                self.tasks_obj.add_task_path_pipe(task)

    def register_scheduled_actions(
        self,
        scheduled_actions: list[ScheduledActionModel] | None = None,
        _: list | None = None,
    ):
        """Register scheduled actions."""
        scheduled_actions = scheduled_actions or []
        # for scheduled_action in default[:]:
        #     middleware_instance = self.all_supported_middleware.get(middleware)
        #     self._middleware[type(middleware_instance)] = middleware_instance
        names = [action.name for action in scheduled_actions]
        if len(names) != len(set(names)):
            ex_msg = 'Scheduled actions must have unique names.'
            raise RuntimeError(ex_msg)
        for action in scheduled_actions or []:
            if action:
                job = schedule.every(action.interval.total_seconds()).seconds.do(
                    action.fn, **action.kwargs
                )
                self._jobs[action.name] = job

    def register_middleware(
        self,
        middleware_list: list | None = None,
        default: list[MIDDLEWARE] | None = None,
    ):
        """Register middleware."""
        middleware_list = middleware_list or []
        default = default or []

        for middleware in default[:]:
            middleware_instance = self.all_supported_middleware.get(middleware)
            self._middleware.append(middleware_instance)
        self._middleware.extend(middleware_list)

        for middleware in self._middleware:
            if middleware:
                self.app.add_middleware(middleware)

    @property
    def message_broker_settings(self):
        """Return the message broker settings."""
        ex_msg = (
            'message_broker_settings property if message broker is '
            'being used must be implemented in child class.'
        )
        raise NotImplementedError(ex_msg)

    @cached_property
    def message_service(self) -> MessageService:
        """Return the message service."""
        topic = self.message_broker_settings.topic
        provider_id = self.message_broker_settings.provider_id

        if not topic or not provider_id:
            ex_msg = 'Message Broker is not configured. Please set the topic and provider_id.'
            raise RuntimeError(ex_msg)

        return MessageService(self.tcex, topic, provider_id)

    def register_message_handlers(
        self,
        handlers: dict[str, object] | None = None,
        default: list[MESSAGE_HANDLERS] | None = None,
    ):
        """Register message handlers."""
        handlers = handlers or {}
        default = default or []

        # for handler in default[:]:
        #     handler_instance = self.all_supported_message_handlers.get(handler)
        #     self._message_handlers[type(handler_instance)] = handler_instance
        # self._message_handlers.update(handlers)
        for feature, handler in self._message_handlers.items():
            if handler:
                self.message_service.add_message_handler(feature, handler)
        self.message_service.listen()

    def _all_supported_types(self, enum: Enum) -> dict[Enum, object]:
        """Return all supported types."""
        return {resource: resource.value.get_resource(self) for resource in enum}

    @cached_property
    def all_supported_routes(self) -> dict[Enum, dict[Enum, object]]:
        """Dynamically returns all supported routes categorized by type."""
        supported_routes = {}

        # Iterate over all top-level categories in ROUTES (e.g., TIE, MESSAGE_HANDLERS)
        for category in ROUTES:
            if not isinstance(category.value, type) or not issubclass(category.value, Enum):
                continue  # Skip non-enum attributes like ALL_TIE

            supported_types = self._all_supported_types(category.value)
            categories_routes = {}
            for item, resource in supported_types.items():
                if resource:
                    categories_routes[item.value.path] = resource
            supported_routes[(category.name.lower())] = categories_routes

        return supported_routes

    @cached_property
    def all_supported_middleware(self) -> dict[MIDDLEWARE, object]:
        """Return all middleware."""
        return self._all_supported_types(MIDDLEWARE)

    @cached_property
    def all_supported_tasks(self) -> dict[TASKS, object]:
        """Return all tasks."""
        return self._all_supported_types(TASKS)

    @cached_property
    def all_supported_message_handlers(self) -> dict[MESSAGE_HANDLERS, object]:
        """Return all message handlers."""
        return {}

    @property
    def log_path(self):
        """Return the log path."""
        return self.model.tc_log_path

    @property
    def falcon_app(self):
        """Return the App Name."""
        msg = 'falcon_app property must be implemented in child class.'
        raise NotImplementedError(msg)

    @property
    def sdk(self):
        """Return the SDK for this TIE App."""
        return None

    @property
    def spec(self):
        """Return the OpenAPI spec."""
        return spec

    def api_event_callback(self, environ, response_handler):
        """Create the API"""
        if not environ['PATH_INFO'].startswith('/'):
            environ['PATH_INFO'] = '/' + environ['PATH_INFO']

        return self.app(environ, response_handler)

    @cached_property
    def settings(self) -> SettingModel:
        """Setting Model."""
        ex_msg = 'settings property must be implemented in child class.'
        raise NotImplementedError(ex_msg)

    @property
    def db_path(self):
        """Return the path JsonDB should use."""
        return self.settings.base_path / 'json_db'

    @cached_property
    def db(self):
        """Return database object."""
        return JsonDB(self.db_path, self.log, json_args={'cls': CustomHandler})

    @abstractmethod
    def initialize_app(self):
        """Initialize the app."""

    @property
    def middleware(self) -> type[MIDDLEWARE]:
        """Return the middleware."""
        return MIDDLEWARE

    @property
    def preflight_checks(self) -> type[PREFLIGHT_CHECKS]:
        """Return the preflight checks."""
        return PREFLIGHT_CHECKS

    @property
    def tasks(self) -> type[TASKS]:
        """Return the tasks."""
        return TASKS

    @property
    def message_handlers(self) -> type[MESSAGE_HANDLERS]:
        """Return the message handlers."""
        return MESSAGE_HANDLERS

    @property
    def routes(self) -> type[ROUTES]:
        """Return the routes."""
        return ROUTES

    def loop_forever(self):
        """Run the app."""
        try:
            self.initialize_app()
            self.preflight_check_service.perform_checks()
        except Exception as ex:
            self.tasks_obj.send_preflight_failure_notification(str(ex)[:80])
            raise
        self.tasks_obj.send_startup_notification()
        if self.migrations:
            self.migrations.migration_service.preform_migrations()

        self._remove_pending_jobs()

        while self.tcex.app.service.message_broker.shutdown is False:
            schedule.run_pending()
            sleep(1)
        delay_time = 30
        deadline = time() + delay_time

        self.log.debug(f'action=loop-forever, shutdown=True, max_delay_time={delay_time}')
        while self.tasks_obj.alive() and time() < deadline:
            sleep(1)

        self.tasks_obj.kill_all()
        self.tcex.exit.exit(ExitCode.SUCCESS, 'App has been successfully Stopped')

    def _remove_pending_jobs(self):
        """Remove pending jobs and reset interrupted in-progress jobs.

        For jobs stuck in "X in progress" status (zombie jobs from server crash):
        - Download tasks: delete the job (no previous state to restore)
        - Other tasks: reset to previous task's "complete" status so they can be retried
        """
        # Build mapping: status_active -> previous task's status_complete
        # This allows resetting interrupted jobs to the previous pipeline stage
        # Only pipe tasks (not standalone) have previous_task_name and status_active
        status_reset_mapping: dict[str, str] = {}
        for task in self.tasks_obj.all():
            task_settings = task.task_settings
            # Standalone tasks don't have previous_task_name; use getattr to safely check
            previous_task_name = getattr(task_settings, 'previous_task_name', None)
            if previous_task_name is not None:
                previous_status_complete = f'{previous_task_name.lower()} complete'
                status_reset_mapping[task_settings.status_active.casefold()] = (
                    previous_status_complete
                )

        def _is_pending(job_request):
            return job_request.status.lower() == self.settings.job.status_pending

        def _is_download_in_progress(job_request):
            if (
                'download' in job_request.status.lower()
                and 'in progress' in job_request.status.lower()
            ):
                return True
            return False

        def _is_resettable_in_progress(job_request):
            """Check if job is in progress and can be reset to previous stage."""
            return job_request.status.casefold() in status_reset_mapping

        jobs = list(self.db.load_all(JobRequestBaseModel))
        for request in jobs:
            if _is_pending(request) or _is_download_in_progress(request):
                self.log.info(f'action=remove-pending-jobs, job-request-id={request.request_id}')
                self.db.delete(request)
            elif _is_resettable_in_progress(request):
                previous_status = status_reset_mapping[request.status.casefold()]
                self.log.info(
                    f'action=reset-interrupted-job, job-request-id={request.request_id}, '
                    f'from-status={request.status}, to-status={previous_status}'
                )
                request.status = previous_status
                self.db.save(request)

    def owner_id(self, owner_name: str) -> int | None:
        """Return the owner id."""
        owners = self.tcex.api.tc.v3.security.owners()
        owners.filter.owner_name(TqlOperator.EQ, owner_name)

        # there should only be one owner
        for owner in owners:
            self.log.debug(f'event=found-owner, owner-id={owner.model.id}, owner-name={owner_name}')
            return owner.model.id

        ex_msg = f'Can not find owner {owner_name} in ThreatConnect instance.'
        raise RuntimeError(ex_msg)
