"""Tasks Common Module"""
# standard library
import gzip
import json
import os
import shutil
import threading
import time
from abc import ABC, abstractmethod
from functools import partial
from typing import TYPE_CHECKING

# third-party
import arrow
from more.database import request_fork_lock
from schema import JobRequestSchema
from tasks.model import TaskSettingPipeModel
from tasks.process_metadata import ProcessMetadata
from tasks.task_abc import TaskABC

if TYPE_CHECKING:
    # standard library
    from pathlib import Path


# pylint: disable=no-member
class TaskPathPipeABC(TaskABC, ABC):
    """Tasks ABC Class

    Flow Path Pipe:

    1. app.__init__()
        a. task gets added via add_task_path_pipe() method
    2. tasks.add_task_path_pipe()
        a. task is scheduled to run task.run_if_able() method
    3. task.run_if_able()
        a. check if task is already running
        b. check if task is paused
        c. calls launch_preflight_checks() method if not running or paused
    4. launch_preflight_checks()
        a. find "next request directory" to process
        b. calls launch() method if directory found
    5. launch()
        a. configures process metadata (partial multi-process)
        b. starts forked process (calls run_pipe_task() method by default)
    6. run_pip_task()
        a. close any open DB sessions
        b. runs task start logic
        c. calls task.run() method
        b. calls task.complete() method
    """

    request_id_file = 'request_id.txt'
    task_settings: TaskSettingPipeModel

    def _check_pause_file(self):
        """Return True if paused requested."""
        super()._check_pause_file()
        if not any([self.task_settings.paused, self.task_settings.paused_file_global]):
            # reset paused_file setting
            self.task_settings.paused_file = False

            # check pause file for the current task
            pipe_task_pause_file = os.path.join(self.task_settings.working_dir_in, 'PAUSE')
            if os.path.exists(pipe_task_pause_file):
                self.log.info(
                    f'task-event-path-pipe=pause, reason=pipe-task-pause-file, '
                    f'task-name={self.task_settings.name}'
                )
                self.task_settings.paused_file = True

    def _create_request_dir(self, request_id: str, priority: str) -> 'Path':
        """Return the a unique directory for a request."""
        # cleanup old task directories
        self._delete_request_dirs(request_id)

        # define dirname using priority, timestamp and request id
        directory_name = f'{self.settings.file_config_separator}'.join(
            [self._get_priority_prefix(priority), str(round(time.time() * 10_000_000)), request_id]
        )
        fqfn: 'Path' = self.task_settings.working_dir_in / directory_name

        # create working directory
        fqfn.mkdir(parents=True, exist_ok=True)

        # create request id file
        self._write_request_id_file(request_id, fqfn)

        return fqfn

    def _delete_request_dirs(self, request_id: str):
        """Delete task directories from previous executions."""
        for directory in self.task_settings.working_dir_in.glob(f'*{request_id}*'):
            if directory.is_dir():
                shutil.rmtree(directory)

    @staticmethod
    def _get_priority_prefix(priority: str) -> str:
        """Return the priority prefix for a request."""
        # NTH - could be an enum
        priority_values = {
            'high': '0',
            'medium': '5',
            'low': '9',
        }
        return priority_values.get(priority, '0')  # default to high

    def _get_request_id(self, fqfn: 'Path') -> str:
        """Return the request id for the current task."""
        return (fqfn / self.request_id_file).open('r').read()

    def _get_request_dir(self, request_id) -> 'Path':
        """Return the newly formatted filename."""
        filename = f'{self.settings.file_config_separator}'.join(
            [str(round(time.time() * 10_000_000)), request_id]
        )
        fqfn: 'Path' = self.task_settings.working_dir_in / filename
        fqfn.mkdir(parents=True, exist_ok=True)
        return fqfn

    @property
    def _next_request_dir(self) -> 'Path':
        """Return the next task directory ordered by filename (date)."""
        for request_dir in sorted(self.task_settings.working_dir_in.iterdir()):
            if request_dir.is_dir():
                self.log.debug(
                    f'task-event-path-pipe=next-request-dir, task-name={self.task_settings.name}, '
                    f'found={request_dir}'
                )
                return request_dir
        else:  # pylint: disable=useless-else-on-loop
            return None

    @staticmethod
    def _fresh_dir(directory: 'Path'):
        """Remove directory if exist and then create new directory."""
        if directory.is_dir():
            shutil.rmtree(str(directory))
        directory.mkdir(parents=True, exist_ok=True)

    @property
    def _task_date_fields_complete(self) -> list[str]:
        """Return list of DB date fields to update when task completes."""
        date_fields = [self.task_settings.date_field_complete]
        if self.task_settings.pipe_task_complete is True:
            date_fields.append(JobRequestSchema.date_completed.name)
        return date_fields

    @property
    def _task_date_fields_start(self) -> list[str]:
        """Return list of DB date fields to update when task starts."""
        date_fields = [self.task_settings.date_field_start]
        if self.task_settings.pipe_task_start is True:
            date_fields.append(JobRequestSchema.date_started.name)
        return date_fields

    def _task_set_status(
        self,
        request_id: str,
        status: str,
        date_fields: list[str],
    ):
        """Update status."""
        now = arrow.utcnow()  # set once for consistency

        # get job request
        job_request = self._db_get_request_by_id(request_id)

        # update status
        job_request.status = status

        # update date fields
        for date_field in date_fields:
            setattr(job_request, date_field, now)

        # patch job request record
        self.db.patch_record(self.session, job_request, 'Failed to update job request status.')

        self.log.info(
            f'task-event-path-pipe=task-set-status, request_id={request_id},status={status}'
        )

    def _task_setup(self, request_dir: 'Path'):
        """Configure task setup."""
        if self.task_settings.pipe_task_start is True:
            # the first task of the pipe doesn't have an input directory
            data_dir = f'{self.task_settings.name_camel}_data'
        else:
            data_dir = f'{self.task_settings.previous_task_name_camel}_data'

        # define the input directory as the previous task output directory
        input_dir = request_dir / data_dir

        # each task needs to know where to find the input and write output
        output_dir = request_dir / f'{self.task_settings.name_camel}_data'

        # cleanup failed prior task executions and create new directory
        self._fresh_dir(output_dir)

        return input_dir, output_dir

    # pylint: disable=arguments-differ
    def _task_start(self, request_id: str):
        """Run tasks startup logic."""
        # rename thread for multiprocessing task
        threading.current_thread().name = f'{self.task_settings.slug}|{request_id}'
        # add new logger for task
        self._task_start_logger()

        self.log.info(
            f'task-event-path-pipe=start, task-name={self.task_settings.slug}, '
            f'request_id={request_id}'
        )

        # set db date fields to be updated
        self._task_set_status(
            request_id,
            self.task_settings.status_active,
            self._task_date_fields_start,
        )

    def _task_complete(self, request_id: str, request_dir: 'Path'):
        """Run tasks startup logic."""
        # set db date fields to be updated
        self._task_set_status(
            request_id,
            self.task_settings.status_complete,
            self._task_date_fields_complete,
        )

        # move to next task
        self.log.info(
            f'task-event-path-pipe=task-complete, action=move-to-next-task, '
            f'task-name={self.task_settings.name}, request_id={request_id}, '
            f'request-dir={request_dir}, working-dir-out={self.task_settings.working_dir_out}'
        )
        shutil.move(str(request_dir), self.task_settings.working_dir_out)

    def _task_complete_failed(self, request_id: str, request_dir: 'Path'):
        """Run tasks startup logic."""
        # set db date fields to be updated
        try:
            self._task_set_status(request_id, 'failed', ['date_failed'])
        except Exception:
            self.log.error(
                'task-event-path-pipe=task-complete-failed, action=failed-to-update-status'
            )

        # move to next task
        self.log.error(
            f'task-event-path-pipe=task-failed, action=move-to-failed-dir, '
            f'task-name={self.task_settings.name}, request_id={request_id}, '
            f'request-dir={request_dir}, working-dir-out={self.task_settings.failed_working_dir}'
        )
        shutil.move(str(request_dir), self.task_settings.failed_working_dir)

    def _write_request_id_file(self, request_id: str, fqfn: 'Path'):
        """Write request id to file."""
        (fqfn / self.request_id_file).open('w').write(request_id)

    def _write_results(self, data: list[dict], output_dir: 'Path', type_: str):
        """Write results to a compressed file."""
        # update the task heartbeat
        self.update_heartbeat()

        # write data to file in output directory (next task input directory)
        with gzip.open(
            output_dir / self._write_results_filename(type_),
            'wt',
            encoding='utf-8',
            compresslevel=9,
        ) as f:
            json.dump(data, f)

    def _write_results_filename(self, file_type) -> str:
        """Return new filename for the given type."""
        name = f'{self.settings.file_config_separator}'.join(
            [str(round(time.time() * 10_000_000)), file_type]
        )
        return f'{name}{self.settings.extension_json}{self.settings.extension_gzip}'

    # pylint: disable=arguments-differ
    def launch(self, request_id: str, request_dir: Path | None = None, **kwargs):
        """Launch the task."""
        # https://docs.sqlalchemy.org/en/14/core/
        # pooling.html#using-connection-pools-with-multiprocessing-or-os-fork

        with request_fork_lock:
            # lunch task
            self.process = self.process_metadata(
                args=(
                    request_id,
                    request_dir,
                ),
                kwargs=kwargs,
                request_id=request_id,
                request_dir=str(request_dir),
            )
            self.process.start()

        self.log.info(
            f'task-event-path-pipe=launch, task-name={self.task_settings.name}, '
            f'pid={self.process.pid}, request-id={request_id}, request-dir={request_dir}'
        )

    def launch_preflight_checks(self):
        """Run pre-flight check before launching task."""
        request_dir = self._next_request_dir
        if request_dir is not None:
            self.log.info(
                f'task-event-path-pipe=launch-preflight-checks, task-name={self.task_settings.name}'
            )
            request_id = self._get_request_id(request_dir)
            self.launch(request_id, request_dir)
        else:
            self.log.trace(
                f'task-event-path-pipe=launch-preflight-check-skip, '
                f'action={self.task_settings.name}, reason=no-request-dir-found, '
                f'working-dir-in={self.task_settings.working_dir_in}'
            )

    @property
    def process_metadata(self):
        """Configure default inputs for process metadata."""
        # update the task heartbeat
        self.update_heartbeat()

        return partial(
            ProcessMetadata,
            args=(),
            daemon=True,
            ns=self.ns,
            max_execution_time_minutes=self.task_settings.max_execution_minutes,
            name=self.task_settings.name,
            target=self.run_pipe_task,
        )

    @abstractmethod
    def run(self, request_id: str, input_dir: 'Path', output_dir: 'Path'):
        """Run the task."""
        raise NotImplementedError('run method must be implemented in child.')

    def run_pipe_task(self, request_id: str, request_dir: 'Path', **kwargs):
        """Run pipe setup, start, and complete logic."""
        # REQUIRED: close session after fork. if session is not closed, I/O errors occur on macos
        self.session.close()

        # run startup logic (rename thread, log action, update status in db)
        try:
            self._task_start(request_id)
        except Exception:
            self.log.exception(
                f'task-event-path-pipe=task-failed, task-name={self.task_settings.name}'
            )

            # run complete failed logic (update status in db, move to next task)
            self._task_complete_failed(request_id, request_dir)

            return

        if self.task_settings.pipe_task_start is True:
            # first task in the pipe needs task directory to be created.
            priority = kwargs.get('priority') or 'high'
            request_dir = self._create_request_dir(request_id, priority=priority)

        # setup task (directories, etc)
        input_dir, output_dir = self._task_setup(request_dir)

        try:
            # run the task core logic
            self.run(request_id, input_dir, output_dir)

            # run complete logic (update status in db, move to next task)
            self._task_complete(request_id, request_dir)
        except Exception:
            self.log.exception(
                f'task-event-path-pipe=task-failed, task-name={self.task_settings.name}'
            )

            # run complete failed logic (update status in db, move to next task)
            self._task_complete_failed(request_id, request_dir)

        return
