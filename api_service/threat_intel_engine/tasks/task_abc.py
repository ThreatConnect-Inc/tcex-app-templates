"""Tasks Common Module"""
# standard library
import logging
import os
import threading
from abc import ABC
from functools import partial
from multiprocessing import Manager
from typing import TYPE_CHECKING, Optional

# third-party
import arrow
import schedule
from more import DbUtil, session
from pydantic import BaseModel
from schema import JobRequestSchema
from tasks.process_metadata import Metadata, ProcessMetadata
from tcex.logger.rotating_file_handler_custom import (  # pylint: disable=no-name-in-module
    RotatingFileHandlerCustom,
)
from tcex.logger.trace_logger import TraceLogger  # pylint: disable=no-name-in-module

if TYPE_CHECKING:
    # third-party
    from model import SettingsModel
    from sqlalchemy.orm import Session
    from tasks.model import TaskSettingModel
    from tcex import TcEx


# pylint: disable=no-member
class TaskABC(ABC):
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
        a. close any open DB sessions
        b. runs task start logic
        c. calls task.run() method
    """

    task_settings: 'TaskSettingModel'

    def __init__(self, settings: 'SettingsModel', tcex: 'TcEx'):
        """Initialize class properties"""
        self.settings: 'SettingsModel' = settings

        # properties
        self.db = DbUtil()
        self.job = None
        self.log: TraceLogger = tcex.log
        self.process: Optional[ProcessMetadata] = None
        self.session: 'Session' = session
        self.ns = Manager().Namespace()
        self.tcex: 'TcEx' = tcex

        # set default heartbeat
        self.ns.heartbeat = None

    def _check_pause_file(self):
        """Return True if paused requested."""
        if self.task_settings.paused is False:
            # reset paused_file_global setting
            self.task_settings.paused_file_global = False

            # check if global pause is enabled
            global_pause_file = os.path.join(os.getcwd(), 'PAUSE')
            if os.path.isfile(global_pause_file):
                self.task_settings.paused_file_global = True

    def _db_get_request_by_id(
        self, request_id: str, method: Optional[str] = 'one_or_none'
    ) -> JobRequestSchema:
        """Return job request for the provided request id.."""
        query = self.session.query(JobRequestSchema).filter_by(request_id=request_id)
        return self.db.get_record(query, method, 'Unexpected error getting request.')

    def _db_increment_counts(self, request_id: str, counts: dict):
        """Update the counts in the DB."""
        query = self.session.query(JobRequestSchema).filter_by(request_id=request_id)
        record = self.db.get_record(query, 'one', 'Unexpected error getting request.')
        for metric_name, metric_count in counts.items():
            current_count = getattr(record, metric_name)
            setattr(record, metric_name, current_count + metric_count)
        self.db.patch_record(self.session, record, 'Unexpected error updating request.')

    def _db_reset_counts(self, request_id: str, fields: list):
        """Update the counts in the DB."""
        query = self.session.query(JobRequestSchema).filter_by(request_id=request_id)
        record = self.db.get_record(query, 'one', 'Unexpected error getting request.')
        for field in fields:
            setattr(record, field, 0)
            self.log.trace(f'event=reset-count, request-id={request_id}, count-name={field}')
        self.db.patch_record(self.session, record, 'Unexpected error updating request.')

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
        for handler in self.tcex.logger._logger.handlers:  # pylint: disable=protected-access
            current_level = handler.level
            break

        # multi-process logging is not supported, shutdown tcex logger and create new logger
        self.tcex.logger.shutdown()

        # new logger
        logging.setLoggerClass(TraceLogger)
        logger = logging.getLogger(self.task_settings.slug)
        logger.setLevel(logging.TRACE)

        # add custom handler
        fh = RotatingFileHandlerCustom(
            filename=self.tcex.inputs.model.tc_log_path / f'task-{self.task_settings.slug}.log',
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

        # update loggers
        self.log = logger
        self.db.log = logger
        self.tcex.log = logger
        setattr(self.tcex, 'logger', logger)

    def update_heartbeat(self):
        """Update the heartbeat."""
        self.ns.heartbeat = arrow.utcnow()
        self.log.trace(
            f'task-event-path-pipe=update-heartbeat, '
            f'heartbeat-value={self.ns.heartbeat}, task={self.task_settings.slug}'
        )

    def cleaner(self):
        """Clean up the task."""

    @property
    def data(self) -> BaseModel:
        """Return data for the task."""
        process = None
        # watchdog_expiration = None
        if self.process is not None and self.process.is_alive():
            process = self.process.metadata

        class _Data(BaseModel):
            """Data model for process."""

            name: Optional[str] = self.task_settings.name
            max_execution_minutes: Optional[int] = self.task_settings.max_execution_minutes
            process: Optional[Metadata]
            schedule_period: Optional[int] = self.task_settings.schedule_period
            schedule_unit: Optional[str] = self.task_settings.schedule_unit

        return _Data(process=process)

    def launch(self, *args, **kwargs):  # pylint: disable=unused-argument
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
        self.task_settings.pause = False

    @property
    def process_metadata(self):
        """Configure default inputs for process metadata."""
        self.ns.heartbeat = arrow.utcnow()
        self.log.trace(
            f'task-event=process-metatdata-set-heartbeat, '
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
        self.task_settings.pause = False

    def run_adhoc(self):
        """Run the task."""
        self.job.run()

    def run_if_able(self):
        """Validate task can run, and if so call launch function."""
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

    def run_task(self, *args, **kwargs):  # pylint: disable=unused-argument
        """Run pipe setup, start, and complete logic."""
        # REQUIRED: close session after fork. if session is not closed, I/O errors occur on macos
        self.session.close()

        # run startup logic (rename thread, log action)
        self._task_start()

        try:
            # run the task core logic
            self.run(*args, **kwargs)
        except Exception:
            self.log.exception(f'task-event=task-failed, task-name={self.task_settings.name}')

    def schedule(self):
        """Schedule the task."""
        # the below is equal to: schedule.every(15).seconds.do(self.run_if_able)
        self.job = schedule.every(self.task_settings.schedule_period)
        self.job: 'schedule.Job' = getattr(self.job, self.task_settings.schedule_unit)
        self.job.do(self.run_if_able)
