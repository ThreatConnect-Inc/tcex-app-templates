"""Tasks Common Module"""

import shutil
import threading
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from core.beacon import provide
from core.task.task_abc import TaskABC
from core.task.task_path_pipe_injectables import (
    CurrentJob,
    TaskInputDir,
    TaskOutputDir,
    UpdateHeartbeat,
)
from core.util.process_metadata import Metadata, ProcessMetadata
from model import AdHocJobRequestModel


class UploadError(Exception):
    """Exception raised for errors while uploading a batch job."""


class UploadRetryError(Exception):
    """Exception raised for errors while polling a batch job."""


class UnrecoverableError(Exception):
    """Exception raised for errors that cannot be recovered from.

    When this exception is raised, the app will:
    1. Mark the job as Failed
    2. Trigger graceful shutdown (pause all tasks, kill running, exit)

    Use this for configuration errors, invalid credentials, or other
    situations where retrying would never succeed.
    """


class TaskTimeoutError(Exception):
    """Exception raised when a task is killed by the watchdog for exceeding max_execution_minutes.

    Distinct from transient errors so that handle_run_error callers can identify
    timeouts and avoid consuming the job's retry budget.
    """


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
    6. run_pipe_task()
        a. close any open DB sessions
        b. runs task start logic
        c. calls task.run() method
        b. calls task.complete() method
    """

    pipe = None
    request_id_file = 'request_id.txt'

    def _check_pause_file(self):
        """Return True if paused requested."""
        super()._check_pause_file()
        if not any([self.task_settings.paused, self.task_settings.paused_file_global]):
            # reset paused_file setting
            self.task_settings.paused_file = False

            # check pause file for the current task
            pipe_task_pause_file = Path(self.task_settings.working_dir_in / 'PAUSE')
            if Path.exists(pipe_task_pause_file):
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
        directory_name = f'{self.settings.file.separator}'.join(
            [
                self._get_priority_prefix(priority),
                str(round(time.time() * 10_000_000)),
                request_id,
            ]
        )
        fqfn: Path = self.task_settings.working_dir_in / directory_name

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
        """Return the request id for the current task.

        Falls back to parsing from directory name if request_id.txt doesn't exist.
        Directory name follows format: priority#timestamp#request_id
        (e.g., 0#17660791302458418#05bedb15-7760-4b7a-b1cd-3b917977160b)
        """
        request_id_path = fqfn / self.request_id_file
        if request_id_path.exists():
            with request_id_path.open('r') as f:
                return f.read()

        # fallback to parsing from directory name (last segment is request_id)
        parts = fqfn.name.split(self.settings.file.separator)
        if parts:
            candidate = parts[-1]
            try:
                UUID(candidate)
                return candidate
            except ValueError:
                pass

        msg = (
            f'Could not determine request_id: {self.request_id_file} not found '
            f'and directory name {fqfn.name} does not contain a valid UUID'
        )
        raise FileNotFoundError(msg)

    def _get_request_dir(self, request_id) -> 'Path':
        """Return the newly formatted filename."""
        filename = f'{self.settings.file.separator}'.join(
            [str(round(time.time() * 10_000_000)), request_id]
        )
        fqfn: Path = self.task_settings.working_dir_in / filename
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
            date_fields.append('date_completed')
        return date_fields

    @property
    def _task_date_fields_start(self) -> list[str]:
        """Return list of DB date fields to update when task starts."""
        date_fields = [self.task_settings.date_field_start]
        if self.task_settings.pipe_task_start is True:
            date_fields.append('date_started')
        return date_fields

    def _task_set_status(
        self,
        request_id: str,
        status: str,
        date_fields: list[str],
    ):
        """Update status."""
        now = datetime.now(UTC)  # set once for consistency

        # get job request
        job_request = self.job_dao.get(request_id)

        # update status
        job_request.status = status

        # update date fields
        for date_field in date_fields:
            setattr(job_request, date_field, now)

        self.db.save(job_request)

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
        """Run tasks completion logic."""
        # set db date fields to be updated
        self._task_set_status(
            request_id,
            self.task_settings.status_complete,
            self._task_date_fields_complete,
        )

        # Clear any backoff/failure state only when the entire pipeline completes.
        # Intermediate task success (e.g., Download succeeding before Convert fails again)
        # should NOT reset failure_count, otherwise the job retries forever at count=1.
        if self.task_settings.pipe_task_complete is True:
            self._clear_failure_state_on_success(request_id)

        # Signal success to Supervisor (via namespace for cross-process communication)
        self.ns.task_result = {'success': True}

        # If this is the last task in the pipeline and job was on probation, clear it
        if self.task_settings.pipe_task_complete is True:
            pipeline = getattr(self, 'pipeline', None)
            if pipeline and self.supervisor.is_probation_job(pipeline, request_id):
                self.supervisor.clear_probation(pipeline)

        # move to next task
        self.log.info(
            f'task-event-path-pipe=task-complete, action=move-to-next-task, '
            f'task-name={self.task_settings.name}, request_id={request_id}, '
            f'request-dir={request_dir}, working-dir-out={self.task_settings.working_dir_out}'
        )
        shutil.move(str(request_dir), self.task_settings.working_dir_out)

    def _task_complete_failed(self, request_id: str, request_dir: 'Path'):
        """Run tasks startup logic.

        `request_dir` is always real here, so the move below is deliberately unguarded.
        Download is the only task that reaches `handle_run_error` without a request dir,
        and it overrides that method to use `_mark_job_failed` instead. Every caller of
        this one — Convert via the base `handle_run_error`, Upload via its own — launches
        through `launch_preflight_checks`, which does not launch without a request dir.
        """
        # set db date fields to be updated
        try:
            self._task_set_status(request_id, 'failed', ['date_failed'])
        except Exception:
            self.log.exception(
                'task-event-path-pipe=task-complete-failed, action=failed-to-update-status'
            )

        # move to next task
        self.log.error(
            f'task-event-path-pipe=task-failed, action=move-to-failed-dir, '
            f'task-name={self.task_settings.name}, request_id={request_id}, '
            f'request-dir={request_dir}, working-dir-out={self.task_settings.failed_working_dir}'
        )
        shutil.move(str(request_dir), self.task_settings.failed_working_dir)

    def _clear_failure_state_on_success(self, request_id: str) -> None:
        """Clear failure tracking state on successful task completion.

        This ensures that if a job previously failed and entered backoff,
        the failure state is reset when it eventually succeeds. This is
        important because:
        - date_failed should reflect the START of a failure streak, not old failures
        - failure_count should reset so future backoff starts at base duration
        - retry_after should be cleared since the job succeeded

        Only updates if any failure state is set (avoids unnecessary DB writes).
        """
        job = self.job_dao.get(request_id)
        if job.date_failed is not None or job.failure_count > 0 or job.retry_after is not None:
            job.date_failed = None
            job.failure_count = 0
            job.retry_after = None
            self.job_dao.save(job)
            self.log.debug(
                f'task-event=cleared-failure-state, '
                f'request_id={request_id}, '
                f'task={self.task_settings.name}'
            )

    def _write_request_id_file(self, request_id: str, fqfn: 'Path'):
        """Write request id to file."""
        with (fqfn / self.request_id_file).open('w') as f:
            f.write(request_id)

    @staticmethod
    def _has_ti_data(data):
        return data.get('group') or data.get('indicator')

    def handle_run_error(
        self, request_id: str, request_dir: Path | None, exception: Exception | None = None
    ):
        """Handle task errors - reset to Pending to restart entire pipeline.

        `request_dir` is None when called from `on_timeout` for a task that had not been
        given one yet (Download — see that method). Only the filesystem cleanup below cares.

        This is the default behavior for non-download tasks (e.g., Convert).
        Download and Upload tasks override this with their own error handling.

        UnrecoverableError: Fail immediately and shutdown (config errors, bad credentials)
        Ad-hoc jobs: Fail immediately (existing behavior)
        Scheduled jobs: Reset to Pending and restart from Download with backoff
        Probation jobs: Trigger immediate shutdown (pipeline was stale on startup)
        """
        job = self.job_dao.get(request_id)

        # Unrecoverable errors always trigger immediate shutdown
        if isinstance(exception, UnrecoverableError):
            self.log.error(f'Unrecoverable error for job {request_id}: {exception}')
            job.status = self.settings.job.status_failed
            job.date_failed = datetime.now(UTC)
            self.job_dao.save(job)

            self.ns.unrecoverable_failure = True
            return

        # Ad-hoc jobs fail immediately - no backoff/retry (existing behavior)
        if isinstance(job, AdHocJobRequestModel):
            self._task_complete_failed(request_id, request_dir)
            return

        # Check if this is a probation job - if so, trigger shutdown
        # Note: pipeline attribute is set in DownloadABC and UploadABC but may not exist here
        pipeline = getattr(self, 'pipeline', None)
        if pipeline and self.supervisor.is_probation_job(pipeline, request_id):
            # Mark job as failed before triggering shutdown
            job.status = self.settings.job.status_failed
            job.date_failed = datetime.now(UTC)
            self.job_dao.save(job)

            self.ns.unrecoverable_failure = True
            self.supervisor.trigger_probation_failure(pipeline, request_id)
            return

        # Scheduled jobs: apply backoff/retry logic with reset to Pending
        now = datetime.now(UTC)
        max_retries = self.settings.app_settings.max_retries

        # Track failure timestamp for logging/debugging
        if job.date_failed is None:
            job.date_failed = now

        job.failure_count += 1
        job.total_retry_count += 1  # Track total retries (never resets)

        # Check if job has exceeded max retries
        if job.failure_count >= max_retries:
            self._task_complete_failed(request_id, request_dir)
            return

        # Compute backoff
        backoff = self.supervisor.compute_backoff(job.failure_count)
        job.retry_after = now + backoff

        # Reset to Retry Pending to restart from Download (clear all stage progress)
        job.status = self.settings.job.status_retry_pending
        job.date_download_start = None
        job.date_download_complete = None
        job.date_convert_start = None
        job.date_convert_complete = None
        job.date_upload_start = None
        job.date_upload_complete = None
        job.count_download_group = 0
        job.count_download_indicator = 0
        # Clear upload-related fields since we're restarting the entire pipeline
        job.count_upload_retries = 0
        job.date_upload_failure = None
        job.upload_failed_files = []
        self.job_dao.save(job)

        # Delete the request directory (will be recreated by Download)
        shutil.rmtree(str(request_dir), ignore_errors=True)

        self.log.warning(
            f'task-event=convert-failure-reset-to-pending, '
            f'request_id={request_id}, '
            f'failure_count={job.failure_count}, '
            f'retry_after={job.retry_after}, '
            f'action=restart-from-download'
        )

    def on_timeout(self) -> None:
        """Update job state after the watchdog kills this task for exceeding max_execution_minutes.

        Runs in the main process because SIGKILL prevents the child from reaching handle_run_error.
        request_id and request_dir are read from process metadata — set at launch time — so there
        is no ambiguity about which job is being cleaned up.

        A timeout means the task published no heartbeat for max_execution_minutes. Every work
        loop beats while it runs, so this is a hang, not slow progress — it is treated as an
        ordinary failure and CONSUMES one retry, which is what lets a permanently wedged job
        reach max_retries and fail for good instead of relaunching forever.
        """
        try:
            request_id = self.process._metadata['request_id']  # noqa: SLF001
            raw_request_dir = self.process._metadata.get('request_dir')  # noqa: SLF001
            # A missing request_dir is legitimate, NOT an error. Download launches before
            # any request directory exists — it is the task that creates one — so it is the
            # only task that can time out without one (Convert and Upload both launch with
            # a directory they are about to consume).
            #
            # This used to `return` here, which meant every Download timeout got no cleanup
            # at all: the job stayed "Download In Progress" with no date_completed or
            # date_failed, the next watchdog tick skipped it for good because the process
            # was already reaped, and _throttle_download() went on counting it as running
            # until throttle_limit hung jobs blocked downloads entirely until restart.
            #
            # Passing None through is safe: handle_run_error only touches request_dir on
            # the move-to-failed path, which is None-guarded below and in _mark_job_failed.
            request_dir = Path(raw_request_dir) if raw_request_dir else None

            # The task can finish between the watchdog's staleness check and the kill.
            # Failing an already-terminal job would report work that reached ThreatConnect
            # as failed, so re-read the record and leave it alone if it is already done.
            #
            # Terminal means completed or genuinely failed — NOT `date_failed is not None`.
            # That field marks the START of a failure streak and is only cleared by
            # `_clear_failure_state_on_success`, which runs only on the pipe's LAST task
            # (`pipe_task_complete`). So a job whose Download failed once and then succeeded
            # still carries date_failed into Convert, and testing it here skipped cleanup for
            # precisely the case this method exists to handle — stranding the job at
            # "<stage> In Progress" until a restart reconciled it.
            job = self.job_dao.get(request_id)
            job_failed = job.status.casefold() == self.settings.job.status_failed.casefold()
            if job.date_completed is not None or job_failed:
                self.log.info(
                    f'task-event=timeout-cleanup-skip, '
                    f'task-name={self.task_settings.name}, '
                    f'request_id={request_id}, status={job.status}, reason=already-terminal'
                )
                return

            self.log.warning(
                f'task-event=timeout-cleanup, '
                f'task-name={self.task_settings.name}, '
                f'request_id={request_id}'
            )
            self.handle_run_error(request_id, request_dir, exception=TaskTimeoutError(request_id))
        except Exception:
            self.log.exception(
                f'task-event=timeout-cleanup-failed, task-name={self.task_settings.name}'
            )

    def launch(self, request_id: str, request_dir: Path | None = None, **kwargs):
        """Launch the task."""
        self.process = self.process_metadata(
            args=(
                request_id,
                request_dir,
            ),
            kwargs=kwargs,
            request_id=request_id,
            # `str(None)` would store the literal 'None', which on_timeout would then
            # turn into Path('None') and operate on a bogus relative path.
            request_dir=str(request_dir) if request_dir is not None else None,
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
    def run(self, request_id: str, input_dir: 'Path', output_dir: 'Path') -> None:
        """Run the task."""
        msg = 'run method must be implemented in child.'
        raise NotImplementedError(msg)

    def run_pipe_task(self, request_id: str, request_dir: 'Path', **kwargs):
        """Run pipe setup, start, and complete logic."""
        # run startup logic (rename thread, log action, update status in db)
        try:
            self._task_start(request_id)
        except Exception as ex:
            self.log.exception(
                f'task-event-path-pipe=task-failed, task-name={self.task_settings.name}'
            )

            # run complete failed logic (update status in db, move to next task)
            self.handle_run_error(request_id, request_dir, exception=ex)

            return

        if self.task_settings.pipe_task_start is True:
            # first task in the pipe needs task directory to be created.
            priority = kwargs.get('priority') or 'high'
            request_dir = self._create_request_dir(request_id, priority=priority)

        # setup task (directories, etc)
        input_dir, output_dir = self._task_setup(request_dir)

        provide(self.update_heartbeat, type_=UpdateHeartbeat)
        provide(output_dir, type_=TaskOutputDir)
        provide(input_dir, type_=TaskInputDir)
        provide(self.db.load(self.request_model, request_id), type_=CurrentJob)

        try:
            # run the task core logic
            self.run(request_id, input_dir, output_dir)

            # run complete logic (update status in db, move to next task)
            self._task_complete(request_id, request_dir)
        except UploadRetryError:
            self.log.exception('task-event=upload-retry-error')
        except Exception as ex:
            self.log.exception(
                f'task-event-path-pipe=task-failed, task-name={self.task_settings.name}'
            )

            # run complete failed logic (update status in db, move to next task)
            self.handle_run_error(request_id, request_dir, exception=ex)

        return

    @property
    def data(self) -> BaseModel:
        """Return data for the task."""
        process = None
        # watchdog_expiration = None
        if self.process is not None and self.process.is_alive():
            process = self.process.metadata

        class _Data(BaseModel):
            """Data model for process."""

            name: str | None = self.task_settings.name
            max_execution_minutes: int | None = self.task_settings.max_execution_minutes
            process: Metadata | None
            schedule_period: int | None = self.task_settings.schedule_period
            schedule_unit: str | None = self.task_settings.schedule_unit
            pipe: str | None = self.pipe

        return _Data(process=process)
