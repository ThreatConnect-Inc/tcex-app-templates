"""Cleaner"""

import shutil
import time
from datetime import UTC, datetime, timedelta
from functools import cached_property
from pathlib import Path

from tcex import TcEx

from core.dao.job_dao import JobRequestDAO
from core.json_db import JsonDB, where
from core.json_db.dao import JsonDBDAO
from core.model.tcvf.settings_model_base import SettingModelBase
from core.model.tie.batch_error_model import BatchErrorModel, JobBatchErrorIndexModel
from core.model.tie.notification_model import NotificationModel
from core.model.tie.task_setting_model import TaskSettingModel
from core.service.error_handling import app_exception
from core.task.task_abc import TaskABC
from core.task.tasks import Tasks


class TaskSettingCustomModel(TaskSettingModel):
    """Custom model for cleaner task settings."""

    max_disk_percent_usage: int
    max_jobs: int
    max_notification_age_days: int


class Cleaner(TaskABC):
    """Clean all working directories and DB entries."""

    def __init__(self, settings: SettingModelBase, tcex: TcEx, db: JsonDB, tasks: Tasks):
        """Initialize class properties."""
        super().__init__(settings, tcex, db)
        self.tasks = tasks
        self.process = None
        self.job_dao = JobRequestDAO(self.db, self.settings)

    @staticmethod
    def _days_to_seconds(days: int) -> int:
        """Convert days to seconds."""
        return days * 24 * 60 * 60

    def _remove_file(self, fqfn: Path):
        """Remove the provide file."""
        try:
            self.log.trace(f'action=file-remove, filename={fqfn}, mtime={fqfn.stat().st_mtime}')
            fqfn.unlink()
        except Exception as ex:
            app_exception(ex, f'failure=failed-removing-file, filename={fqfn.name}')

    def _clean_directories(self, seconds: int):
        """Clean files in the common directories."""
        try:
            # iterate over all contents in "out" directory matching dirs ending with "_working_dir"
            # TODO: In TCVE apps it didnt iterate over nested dirs.
            working_dirs = [
                wd
                for pipeline_dir in Path(self.settings.base_path).glob('*')
                for wd in pipeline_dir.glob('*_working_dir*')
            ]

            for working_dir in working_dirs:
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
        except Exception as ex:
            app_exception(ex, 'failure=failed-cleaning-files')

    def _clean_batch_errors(self):
        """Clean files in the common directories."""
        try:
            job_ids = self.job_dao.get_all_job_ids()
            for batch_error in self.batch_error_dao.get_all(
                where={'request_id': where.not_(where.is_in(job_ids))}
            ):
                self.batch_error_dao.delete(batch_error)
        except Exception as ex:
            # log exception
            app_exception(ex, 'failure=failed-cleaning-batch-errors')

    def _clean_job_requests(self):
        """Clean files in the common directories."""
        try:
            for job in self.job_dao.get_jobs_to_clean(self.task_settings.max_jobs):
                self.log.debug(f'task-event=clean-job-request, job={job}')
                self.job_dao.delete(job)
                try:
                    self.db.delete(self.db.load(JobBatchErrorIndexModel, job.request_id))
                except FileNotFoundError:
                    self.log.warning(
                        'task-event=error-index-not-found, request_id=%s',
                        job.request_id,
                    )
        except Exception as ex:
            # log exception
            app_exception(ex, 'failure=failed-cleaning-job-request')

    @property
    def _disk_usage(self) -> int:
        """Return True if the disk usage has been exceeded."""
        # percent_used = used / total * 100 = percent used
        stat = shutil.disk_usage(self.settings.base_path)
        return int(stat.used / stat.total * 100)

    def launch(self):
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
        self._clean_batch_errors()

        # only launch cleaner if disk usage is greater than defined percentage
        # remove directories until disk usage is less than defined percentage or 2 days
        for days in reversed(range(2, 90)):  # TODO make a setting
            percent_used = self._disk_usage
            seconds = self._days_to_seconds(days)
            if percent_used >= self.task_settings.max_disk_percent_usage:
                self.log.info(
                    f'task-event=launch-preflight-check, action={self.task_settings.name}, '
                    f'base-path={self.settings.base_path}, days={days}, '
                    f'percent-used={percent_used}%'
                )
                self._clean_directories(seconds)
            else:
                self.log.trace(
                    f'task-event=launch-preflight-check-skip, action={self.task_settings.name}, '
                    f'max-disk-percent-usage={self.task_settings.max_disk_percent_usage}, '
                    f'reason=disk-usage-under-max-percent, percent-used={percent_used}, '
                )
                break

    def _clean_notifications(self):
        """Remove notifications older than max_notification_age_days."""
        try:
            cutoff = datetime.now(UTC) - timedelta(
                days=self.task_settings.max_notification_age_days
            )
            for notification in self.db.load_all(
                NotificationModel,
                where=lambda n: n.date_added < cutoff,
            ):
                self.db.delete(notification)
        except Exception as ex:
            app_exception(ex, 'failure=failed-cleaning-notifications')

    def run(self):
        """Run the task."""
        for task in self.tasks.all():
            task.cleaner()
        self._clean_notifications()

    @cached_property
    def batch_error_dao(self) -> JsonDBDAO:
        """Return a new instance of the DAO."""
        return JsonDBDAO(self.db, BatchErrorModel)

    @cached_property
    def task_settings(self) -> 'TaskSettingCustomModel':
        """Return the task settings."""
        return TaskSettingCustomModel(
            description='Cleans the filesystem and the database.',
            max_execution_minutes=30,
            name='Cleaner',
            schedule_period=2,
            schedule_unit='hours',
            max_disk_percent_usage=60,
            max_jobs=500,
            max_ttl_batch_error=(60 * 60 * 24 * 90),  # 90 days
            max_notification_age_days=30,
        )
