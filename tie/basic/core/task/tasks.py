"""Tasks Container"""

# standard library
import logging
import os
import signal
import time
import traceback
from datetime import UTC, timedelta
from typing import TYPE_CHECKING, ClassVar

# third-party
import arrow
import schedule
from tcex import TcEx
from tcex.exit import ExitCode

# first-party
from core.beacon import inject
from core.dao.job_dao import JobRequestDAO
from core.json_db import JsonDB
from core.model.settings_model_base import SettingModelBase
from core.supervisor import Supervisor

if TYPE_CHECKING:
    # first-party
    from task import TaskABC

logger = logging.getLogger('tcex')


class Tasks:
    """Tasks Container"""

    status_final: ClassVar[list[str]] = []

    def __init__(
        self,
        tcex: TcEx,
        db: JsonDB = inject(JsonDB),
        settings: SettingModelBase = inject(SettingModelBase),
    ):
        """Initialize class properties.

        Args:
            tcex: TcEx instance.
            db: JsonDB instance for persisting Supervisor state.
            settings: Application settings.
        """
        # properties
        self._tasks = set()
        self.log = logger
        self.tcex = tcex
        self.exit_service = tcex.exit
        self.settings = settings
        self.db = db

        # Create JobRequestDAO for Supervisor
        self.job_dao = JobRequestDAO(db, settings)

        # Initialize Supervisor with JsonDB, job_dao, settings, and exit service
        self.supervisor = Supervisor(
            db=db,
            job_dao=self.job_dao,
            settings=settings,
            exit_service=self.exit_service,
        )

        # Check for stale pipelines and enter probation mode if needed
        # Stale pipelines: first job must succeed or app shuts down
        # Healthy pipelines: baseline is reset normally
        self.supervisor.check_and_enter_probation()

        # schedule watchdog for tasks
        schedule.every(1).minute.do(self.watchdog)

    def add_task(self, task: 'TaskABC'):
        """Add a task to the container."""
        self._tasks.add(task)
        task.schedule()

    def add_task_path_pipe(self, tasks: 'list[TaskABC]'):
        """Add a task to the container."""
        for index, task in enumerate(tasks):  # reverse list
            # set the task index
            task.task_settings.index = index

            # first task in pipe
            if index == 0:
                task.task_settings.pipe_task_start = True
            else:
                # set previous task name for pipe, unless first task in pipe
                task.task_settings.previous_task_name = tasks[index - 1].task_settings.name

            # last task in pipe
            if index == len(tasks) - 1:
                task.task_settings.pipe_task_complete = True

                # for last task in pipe, set the pipe task complete to True
                task.task_settings.working_dir_out = (
                    task.task_settings.base_path / 'done_working_dir'
                )
                task.task_settings.working_dir_out.mkdir(parents=True, exist_ok=True)

                # add final status
                Tasks.status_final.append(task.task_settings.status_complete)
            else:
                # out directory for the current task is the "in" directory for
                # the next task, except when on the last task in the pipe
                task.task_settings.working_dir_out = tasks[index + 1].task_settings.working_dir_in

            self.log.debug(
                f'pipe-event=add-task-pipe, task-name={task.task_settings.name}, '
                f'pipe-task-start={task.task_settings.pipe_task_start}, '
                f'pipe-task-complete={task.task_settings.pipe_task_complete}, '
                f'previous-task-name={task.task_settings.previous_task_name}, '
                f'working-dir-out={task.task_settings.working_dir_out}'
            )
            self.add_task(task)

    def all(self) -> 'list[TaskABC]':
        """Return all processes that are alive."""
        return list(self._tasks)

    def alive(self) -> 'list[TaskABC]':
        """Return all processes that are alive."""
        return [t for t in self._tasks if t.process is not None and t.process.is_alive()]

    def kill(self, task: 'TaskABC'):
        """Kill multi-processes to cleanly exit app."""
        self.log.warning(f'event=kill-task, task-name={task.task_settings.name}')
        if task.process is not None:
            if task.process.is_alive():
                try:
                    self._send_signal_to_task(signal.SIGALRM, task)
                    time.sleep(2)
                    self._send_signal_to_task(signal.SIGKILL, task)
                except Exception:
                    self.log.warning(f'event=kill-task-failed, pid={task.process.pid}')
                    self.log.warning(traceback.format_exc())

            task.process.join(10)

    def kill_all(self):
        """Kill all multi-process."""
        max_wait = 30
        deadline = time.time() + max_wait

        # wait for up to "max_wait"
        self.log.trace(f'action=kill_all-wait-for-task-completion, max-seconds={max_wait}')
        while True:
            # allow processes to wrap up current work before exiting App
            if time.time() > deadline or len(self.alive()) == 0:
                break
            time.sleep(1)
        for task in self.all():
            self.kill(task)

    def watchdog(self) -> None:
        """Monitor tasks and perform health checks.

        Per-job backoff is handled directly on JobRequestModel fields.
        Pipeline staleness is checked by Supervisor.tick() using job completion times.
        """
        self.log.debug(f'task-event=run-watchdog, task-count={len(self._tasks)}')
        api_limit: None | dict = None

        # Run Supervisor tick for pipeline health monitoring
        # This checks if any pipeline has no completed jobs for threshold (default 48h)
        self.supervisor.tick()

        # Check for shutdown request from Supervisor (staleness detected in main process)
        if self.supervisor.shutdown_requested:
            self.log.warning(
                f'task-event=supervisor-shutdown-requested, '
                f'reason={self.supervisor.shutdown_reason}'
            )
            self._graceful_shutdown(self.supervisor.shutdown_reason)
            return

        # Check for unrecoverable failure from forked tasks (cross-process via Redis)
        for task in self.all():
            if task.ns.unrecoverable_failure is True:
                self.log.warning(
                    f'task-event=unrecoverable-failure, task-name={task.task_settings.name}'
                )
                self._graceful_shutdown('Task reported unrecoverable failure')
                return

        for task in self.all():
            # see if we should kill the task as its over its time limit
            if task.process is not None and task.process.is_alive():
                # update date expires based on heartbeat
                # pylint: disable=protected-access
                self.log.trace(
                    f'task-event=watchdog, '
                    f'heartbeat-value={task.ns.heartbeat}, task={task.task_settings.name}'
                )

                if arrow.now(UTC) - task.ns.heartbeat > timedelta(
                    minutes=task.task_settings.max_execution_minutes
                ):
                    self.log.warning(
                        f'task-event=kill-task, task-name={task.task_settings.name}, '
                        f'process-id={task.process.pid}, metadata={task.process.metadata.dict()}, '
                    )
                    self.kill(task)

                # Handle setting our api limit hit metric since its forked
                # We only care about the value for the DownloadPathPipe task
                if type(task).__name__ in ['Download']:
                    self.log.debug(f'Task: {type(task).__name__} has: {task.ns.api_limit_details}')
                    # Set to latest value
                    if api_limit is None or task.ns.api_limit_details.get(
                        'date_set'
                    ) > api_limit.get('date_set'):
                        api_limit = task.ns.api_limit_details

            if api_limit is not None:
                # self.tcex.app.service.add_metric(
                #     'Vulnerability API Limit Hit', api_limit.get('reached')
                # )
                self.log.debug(f'API Limit Hit: {api_limit.get("reached")}')

    def pause_all(self):
        """Pause all tasks.

        Sets pause flag in Tasks' settings so that it will not persist across restart.
        """
        for task in self.all():
            task.task_settings.paused = True

    def _graceful_shutdown(self, reason: str) -> None:
        """Perform graceful shutdown: pause tasks, kill running, then exit.

        Args:
            reason: Human-readable reason for shutdown.
        """
        self.log.error(f'task-event=graceful-shutdown-initiated, reason={reason}')
        self.pause_all()
        self.kill_all()
        if self.exit_service:
            self.exit_service.exit(ExitCode.FAILURE, f'Shutting down: {reason}')

    def _send_signal_to_task(self, send_signal: signal.Signals, to_task: 'TaskABC'):
        """Send signal to task."""
        if to_task.process is None or not to_task.process.is_alive():
            self.log.warning(
                f'event=send-signal-to-task-failed, task-name={to_task.task_settings.name}, '
                f'reason=task-not-running'
            )
            return
        self.log.trace(
            f'event=send-signal-to-task, signal={send_signal}, '
            f'task-name={to_task.task_settings.name}, pid={to_task.process.pid}'
        )
        os.kill(to_task.process.pid, send_signal)
