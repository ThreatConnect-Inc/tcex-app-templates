"""Tasks Container"""
# standard library
import logging
import os
import signal
import traceback
from datetime import timedelta
from typing import TYPE_CHECKING

# third-party
import arrow
import schedule

if TYPE_CHECKING:
    # third-party
    from tasks import TaskABC

logger = logging.getLogger('tcex')


class Tasks:
    """Tasks Container"""

    status_final: list[str] | None = []

    def __init__(self):
        """Initialize class properties."""

        # properties
        self._tasks = set()
        self.log = logger

        # schedule watchdog for tasks
        schedule.every(1).minute.do(self.watchdog)

    def add_task(self, task: 'TaskABC'):
        """Add a task to the container."""
        self._tasks.add(task)
        task.schedule()

    def add_task_path_pipe(self, tasks: list['TaskABC']):
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

    def all(self) -> list['TaskABC']:
        """Return all processes that are alive."""
        return self._tasks

    def alive(self) -> list['TaskABC']:
        """Return all processes that are alive."""
        return [t for t in self._tasks if t.process is not None and t.process.is_alive()]

    def kill(self, task: 'TaskABC'):
        """Kill multiprocess to cleanly exit app."""
        if task.process is not None:
            if task.process.is_alive():
                try:
                    os.kill(task.process.pid, signal.SIGKILL)
                except Exception:
                    self.log.warning(f'event=kill-task-failed, pid={task.process.pid}')
                    self.log.warning(traceback.format_exc())

            task.process.join()

    def kill_all(self):
        """Kill all multiprocess."""
        for task in self._tasks:
            self.kill(task)

    def watchdog(self) -> list['TaskABC']:
        """Return all processes that are alive."""
        self.log.debug(f'task-event=run-watchdog, task-count={len(self._tasks)}')
        for task in self.all():
            if task.process is not None and task.process.is_alive():
                self.log.trace(
                    f'task-event=watchdog, '
                    f'heartbeat-value={task.ns.heartbeat}, task={task.task_settings.name}'
                )

                if arrow.utcnow() - task.ns.heartbeat > timedelta(
                    minutes=task.task_settings.max_execution_minutes
                ):
                    self.log.warning(
                        f'task-event=kill-task, task-name={task.task_settings.name}, '
                        f'process-id={task.process.pid}, metadata={task.process.metadata.dict()}, '
                    )
                    self.kill(task)
