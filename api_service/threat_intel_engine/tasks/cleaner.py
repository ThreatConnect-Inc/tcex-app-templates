"""Cleaner"""
# standard library
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING

# third-party
from schema import JobRequestSchema
from tasks.model import TaskSettingModel
from tcex.backports import cached_property

from .task_abc import TaskABC

if TYPE_CHECKING:
    # third-party
    from pydantic import BaseModel
    from tcex import TcEx

    from .tasks import Tasks


class TaskSettingCustomModel(TaskSettingModel):
    """Custom model for cleaner task settings."""

    max_disk_percent_usage: int
    max_ttl_job_request: int


class Cleaner(TaskABC):
    """Task Module

    Download Task Flow:

    1. launch_preflight_checks - run pre-flight checks before launching task (run method)
    2. launch - launch task, typically as multiprocessing.Process
    3. run - task entry point

    The cleaner task will remove files from the working directory if the disk space is greater than
    max_disk_percent_usage. The cleaner starts with dirs 31 days old and iterates down to 2 days
    old, stopping when the disk space is less than max_disk_percent_usage. The cleaner will also
    remove job request in the database that are older than max_ttl_job_request.
    """

    def __init__(self, settings: 'BaseModel', tcex: 'TcEx', tasks: 'Tasks'):
        """Initialize class properties."""
        super().__init__(settings, tcex)
        self.tasks = tasks

    @staticmethod
    def _days_to_seconds(days: int) -> int:
        """Convert days to seconds."""
        return days * 24 * 60 * 60

    def _remove_file(self, fqfn: Path):
        """Remove the provide file."""
        try:
            self.log.trace(f'action=file-remove, filename={fqfn}, mtime={fqfn.stat().st_mtime}')
            fqfn.unlink()
        except Exception:
            self.log.exception(f'failure=failed-removing-file, filename={fqfn.name}')

    def _clean_directories(self, seconds: int):
        """Clean files in the common directories."""
        try:
            # iterate over all contents in "out" directory matching dirs ending with "_working_dir"
            for working_dir in Path(self.settings.base_path).glob('*_working_dir*'):
                # skip files
                if not working_dir.is_dir():
                    continue

                # iterate over contents in the working directory
                # processing/deleting request directories (timestamp#request_id)
                for request_dir in working_dir.iterdir():
                    # skip files
                    if not request_dir.is_dir():
                        continue

                    # get the age of the request directory
                    dir_age = time.time() - request_dir.stat().st_mtime
                    if dir_age > seconds:
                        self.log.info(
                            'task-event=remove-dir, '
                            f'directory={request_dir.resolve()}, '
                            f'dir-age={dir_age}, '
                            f'max-ttl={seconds}'
                        )
                        shutil.rmtree(request_dir)
        except Exception:
            self.log.exception('failure=failed-cleaning-files')

    def _clean_job_requests(self):
        """Remove job requests from DB older than mx_ttl_job_request."""
        try:
            query = self.session.query(JobRequestSchema)  # pylint: disable=no-member
            jobs = self.db.get_record(query, 'all', 'Unexpected error querying job requests.')
            for job in jobs:
                done_date = job.date_completed or job.date_failed
                if (
                    done_date is not None
                    and time.time() - done_date.timestamp() > self.task_settings.max_ttl_job_request
                ):
                    self.session.delete(job)  # pylint: disable=no-member
                    self.session.commit()  # pylint: disable=no-member
        except Exception:
            # log exception
            self.log.exception('failure=failed-cleaning-job-request')

    @property
    def _disk_usage(self) -> int:
        """Return True if the disk usage has been exceeded."""
        # percent_used = used / total * 100 = percent used
        stat = shutil.disk_usage(self.settings.base_path)
        return round(stat.used / stat.total * 100, 2)

    def launch(self):  # pylint: disable=arguments-differ
        """Launch the task."""
        self.process = self.process_metadata()
        self.process.start()
        self.log.info(f'task-event={self.task_settings.name}, pid={self.process.pid}')

    def launch_preflight_checks(self):
        """Run pre-flight check before launching task."""
        self.launch()

    def cleaner(self):
        """Run the general cleaner task."""
        # clean db
        self._clean_job_requests()

        # only launch cleaner if disk usage is greater than defined percentage
        # remove directories until disk usage is less than defined percentage or 2 days
        for days in reversed(range(2, 31)):
            percent_used = self._disk_usage
            seconds = self._days_to_seconds(days)
            if percent_used >= self.task_settings.max_disk_percent_usage:
                self.log.info(
                    f'task-event=launch-preflight-check, action={self.task_settings.slug}, '
                    f'base-path={self.settings.base_path}, days={days}, '
                    f'percent-used={percent_used}%'
                )
                self._clean_directories(seconds)
            else:
                self.log.trace(
                    f'task-event=launch-preflight-check-skip, action={self.task_settings.slug}, '
                    f'max-disk-percent-usage={self.task_settings.max_disk_percent_usage}, '
                    f'reason=disk-usage-under-max-percent, percent-used={percent_used}%, '
                )
                break

    def run(self):
        """Run the task.

        Each task can have their own cleaner method. This is not required, but if the task
        has a cleaner method, it will be called here.
        """
        for task in self.tasks.all():
            # task will be automatically killed if they don't update the heartbeat timestamp
            # before the max_execution_minutes period. this method all will update the heartbeat.
            self.update_heartbeat()

            task.cleaner()

    @cached_property
    def task_settings(self) -> 'TaskSettingCustomModel':
        """Return the task settings.

        Tasks have standard model that is used to define the task settings. This method returns
        the settings model for the download task. Any additional settings can be defined in this
        property.

        The start and end date fields in the database are defined here and are automatically updated
        by the task manager when the task is started and completed.
        """

        return TaskSettingCustomModel(
            description='Cleans the filesystem and the database.',
            max_execution_minutes=20,
            name='Cleaner',
            schedule_period=15,
            schedule_unit='minutes',
            # additional properties
            max_disk_percent_usage=60,
            max_ttl_job_request=(60 * 60 * 24 * 30),  # 30 days
        )
