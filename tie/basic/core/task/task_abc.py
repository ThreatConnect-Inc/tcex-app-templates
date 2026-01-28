"""Tasks Common Module"""

# standard library
import logging
import pickle  # nosec
import threading
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from functools import cached_property, partial
from pathlib import Path
from typing import Generic, Protocol, TypeVar

# third-party
import arrow
import schedule
from pydantic.main import BaseModel
from tcex import TcEx
from tcex.logger.rotating_file_handler_custom import (
    RotatingFileHandlerCustom,  # pylint: disable=no-name-in-module
)
from tcex.logger.trace_logger import TraceLogger  # pylint: disable=no-name-in-module

# first-party
from core.beacon import inject, provide
from core.dao.job_dao import JobRequestDAO
from core.json_db import JsonDB
from core.model.tie.job_request_base_model import JobRequestBaseModel
from core.model.tie.task_setting_pipe_model import TaskSettingPipeModel
from core.service.writing_service import WritingService
from core.supervisor import Supervisor
from core.task.task_path_pipe_injectables import UpdateHeartbeat
from core.util.process_metadata import Metadata, ProcessMetadata
from model.settings_model import SettingModel

T = TypeVar('T', bound=JobRequestBaseModel)

# pylint: disable=no-member


class TaskResult(Protocol):
    """Task Result Protocol - signals success or failure to main process."""

    success: bool
    error_type: str | None
    error_message: str | None


class TaskNamespace(Protocol):
    """Task Namespace Protocol"""

    api_limit_details: dict
    heartbeat: arrow.Arrow | None
    last_batch_failure: datetime | None
    task_result: TaskResult | None  # None=no event, set on success or failure
    unrecoverable_failure: bool


class TaskData(BaseModel):
    """Data model for process."""

    process: Metadata | None
    name: str | None
    max_execution_minutes: int | None
    schedule_period: int | None
    schedule_unit: str | None


class TaskABC(ABC, Generic[T]):
    """Tasks ABC Class

    Flow:

    1. app.__init__()
        a. task gets added via add_task_path_pipe() method
    2. tasks.add_task()
        a. task is scheduled to run task.run_if_able() method
    3. task.run_if_able()
        a. check if task is already running
        b. check if task is paused
        c. calls launch_preflight_checks() method if not running or paused
    4. launch_preflight_checks()
        a. run checks to see if task can run
        b. call launch() method if checks pass
    5. launch()
        a. configures process metadata (partial multi-process)
        b. starts forked process (calls run_task() method by default)
    6. run_task()
        b. runs task start logic
        c. calls task.run() method
    """

    # If the backfill reports task requires the files to have been previously downloaded, then
    # use this path to store the downloaded files.
    _REPORT_FOLDER_NAME: str = 'report_working_dir'

    def __init__(
        self,
        settings: SettingModel = inject(SettingModel),
        tcex: TcEx = inject(TcEx),
        db: JsonDB = inject(JsonDB),
        supervisor: Supervisor = inject(Supervisor),
        *,
        request_schema: type[T] = JobRequestBaseModel,
    ):
        """Initialize class properties"""
        self.settings = settings
        self.supervisor = supervisor

        # properties
        self.db = db
        self.job = None
        self.log: TraceLogger = tcex.log
        self.process: ProcessMetadata | None = None
        self.request_model: type[T] = request_schema
        self.tcex: TcEx = tcex
        self.job_dao = JobRequestDAO(self.db, self.settings, request_schema)
        self.writing_service = WritingService(self.db, self.log)
        # create after tcex is init
        self.ns = self.namespace

        # set default heartbeat
        self.ns.heartbeat = None
        self.ns.unrecoverable_failure = False
        self.ns.task_result = None
        self.ns.last_batch_failure = datetime.now(UTC) - timedelta(days=90)

        # set default api limit details
        self.ns.api_limit_details = {
            'reached': 'False',
            'date_set': arrow.Arrow.now(UTC),
        }

    @cached_property
    def namespace(self) -> TaskNamespace:
        """Create a redis namespace for this task."""
        context = str(uuid.uuid4())
        redis_client = self.tcex.app.key_value_store.redis_client

        class RedisNamespace:
            """Redis Namespace"""

            def __getattr__(self, name):
                """Get value from redis."""
                value = redis_client.hget(context, name)
                return pickle.loads(value) if value is not None else None  # nosec

            def __setattr__(self, name, value):
                """Set value in redis."""
                if value is not None:
                    redis_client.hset(context, name, pickle.dumps(value))  # nosec

        return RedisNamespace()  # type: ignore

    @cached_property
    @abstractmethod
    def task_settings(self) -> TaskSettingPipeModel:
        """Return the task settings."""

    def _check_pause_file(self):
        """Return True if paused requested."""
        if self.task_settings.paused is False:
            # reset paused_file_global setting
            self.task_settings.paused_file_global = False

            # check if global pause is enabled
            global_pause_file = Path.cwd() / 'PAUSE'
            self.task_settings.paused_file_global = global_pause_file.is_file()

    def _db_increment_counts(self, request, counts: dict):
        """Update the counts in the self.db."""
        for metric_name, metric_count in counts.items():
            current_count = getattr(request, metric_name)
            setattr(request, metric_name, current_count + metric_count)
        self.db.save(request)

    def _db_reset_counts(self, request: JobRequestBaseModel, fields: list):
        """Update the counts in the self.db."""
        for field in fields:
            setattr(request, field, 0)
            self.log.trace(
                f'event=reset-count, request-id={request.request_id}, count-name={field}'
            )
        self.db.save(request)

    def _task_start(self):
        """Run tasks startup logic."""
        # rename thread for multiprocessing task
        threading.current_thread().name = self.task_settings.slug
        # add new logger for task
        self._task_start_logger()
        self.log.info(f'task-event=start, task-name={self.task_settings.slug}')

    def _task_start_logger(self):
        """Add new logger specifically for current task."""
        # get current log level from tcex, this value can be dynamically changed. the current
        # task will keep the existing log level, but new tasks will use the new log level.
        for handler in self.tcex.logger._logger.handlers:  # noqa: SLF001
            current_level = handler.level
            break

        # multi-process logging is not supported, shutdown tcex logger and create new logger
        self.tcex.logger.shutdown()

        # new logger
        logging.setLoggerClass(TraceLogger)
        logger = logging.getLogger(self.task_settings.slug)
        logger.setLevel(logging.TRACE)  # pylint: disable=no-member

        # add custom handler
        fh = RotatingFileHandlerCustom(
            filename=str(
                self.tcex.inputs.model.tc_log_path / f'task-{self.task_settings.slug}.log'
            ),
            maxBytes=10_485_760,
            backupCount=5,
        )
        fh.set_name(self.task_settings.slug)
        fh.setFormatter(
            logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)8s - %(message)s '
                '(%(filename)s:%(funcName)s:%(lineno)d:%(threadName)s)'
            )
        )
        fh.setLevel(current_level)
        logger.addHandler(fh)
        self.tcex._log.addHandler(fh)  # noqa: SLF001

    def update_heartbeat(self, verbose=True):
        """Update the heartbeat."""
        self.ns.heartbeat = arrow.now(UTC)
        if verbose:
            self.log.trace(
                f'task-event-path-pipe=update-heartbeat, '
                f'heartbeat-value={self.ns.heartbeat}, task={self.task_settings.slug}'
            )

    def cleaner(self):
        """Clean up the task."""

    @property
    def data(self) -> TaskData:
        """Return data for the task."""
        process = None
        # watchdog_expiration = None
        if self.process is not None and self.process.is_alive():
            process = self.process.metadata

        return TaskData(
            process=process,
            name=self.task_settings.name,
            max_execution_minutes=self.task_settings.max_execution_minutes,
            schedule_period=self.task_settings.schedule_period,
            schedule_unit=self.task_settings.schedule_unit,
        )

    def launch(self, *args, **kwargs):  # noqa: ARG002
        """Launch the task."""
        self.process = self.process_metadata()
        self.process.start()
        self.log.trace(f'task-event={self.task_settings.name}, pid={self.process.pid}')

    def launch_preflight_checks(self):
        """Validate if the task should run."""
        self.log.trace(f'task-event=launch-preflight-check, task-name={self.task_settings.name}')
        self.launch()

    @property
    def pause(self):
        """Return True if paused requested."""
        self.task_settings.paused = False

    @property
    def process_metadata(self):
        """Configure default inputs for process metadata."""
        self.ns.heartbeat = arrow.now(UTC)
        self.log.trace(
            f'task-event=process-metadata-set-heartbeat, '
            f'heartbeat-value={self.ns.heartbeat}, task={self.task_settings.name}'
        )
        return partial(
            ProcessMetadata,
            args=(),
            daemon=True,
            ns=self.ns,
            max_execution_time_minutes=self.task_settings.max_execution_minutes,
            name=self.task_settings.name,
            target=self.run_task,
        )

    @property
    def resume(self):
        """Return True if paused requested."""
        self.task_settings.paused = False

    @abstractmethod
    def run(self):
        """Run the task."""

    def run_adhoc(self):
        """Run the task."""
        self.job.run()

    def run_if_able(self):
        """Validate task can run, and if so call launch function."""
        try:
            if self.process is not None:
                if self.process.is_alive():
                    return  # launch is prohibited if process is currently alive
                self.process.join()

            # run check for pause files
            self._check_pause_file()

            # there are 3 ways an app can be paused
            # 1. pause setting set manually
            # 2. pause file exists
            # 3. global pause file exists
            if any(
                [
                    self.task_settings.paused,
                    self.task_settings.paused_file,
                    self.task_settings.paused_file_global,
                ]
            ):
                # either global pause is enabled or task specific pause is enabled
                self.log.info(
                    f'task-event-path=run-if-able, task-name={self.task_settings.name}, '
                    f'paused={self.task_settings.paused}, '
                    f'paused-file={self.task_settings.paused_file}, '
                    f'paused-file-global={self.task_settings.paused_file_global}'
                )
                return

            self.launch_preflight_checks()
        except Exception:
            self.log.exception('task-event=run-if-able-error')

    def run_task(self, *args, **kwargs):  # pylint: disable=unused-argument
        """Run pipe setup, start, and complete logic."""
        # run startup logic (rename thread, log action)
        self._task_start()
        provide(self.update_heartbeat, type_=UpdateHeartbeat)
        try:
            # run the task core logic
            self.run(*args, **kwargs)
        except Exception:
            self.log.exception(f'task-event=task-failed, task-name={self.task_settings.name}')

    def schedule(self):
        """Schedule the task."""
        # the below is equal to: schedule.every(15).seconds.do(self.run_if_able)
        self.job = schedule.every(self.task_settings.schedule_period)
        self.job: schedule.Job = getattr(self.job, self.task_settings.schedule_unit)
        self.job.do(self.run_if_able)


# how TQL handles multiple attributes
