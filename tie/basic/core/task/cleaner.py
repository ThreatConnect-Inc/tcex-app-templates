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
from core.json_db.json_db import SortOrder
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
    max_done_working_dir_size_bytes: int
    max_job_age_days: int
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

    def _job_request_dirs(self, dirname: str) -> list[Path]:
        """Return the request directories under the given base_path child directory."""
        working_dir = Path(self.settings.base_path) / dirname
        return [d for d in working_dir.glob('*') if d.is_dir()]

    @staticmethod
    def _dir_size(path: Path) -> int:
        """Return the total size, in bytes, of all files under path."""
        return sum(f.stat().st_size for f in path.rglob('*') if f.is_file())

    def _remove_request_dir(self, request_dir: Path):
        """Remove the given job request directory."""
        self.log.info(f'task-event=remove-dir, directory={request_dir.resolve()}')
        shutil.rmtree(request_dir)

    def _trim_by_size(self, dirs: list[Path], max_bytes: int):
        """Remove oldest dirs first until the total size of dirs is under max_bytes."""
        dirs = sorted(dirs, key=lambda d: d.stat().st_mtime)
        total = sum(self._dir_size(d) for d in dirs)
        for request_dir in dirs:
            if total <= max_bytes:
                break
            total -= self._dir_size(request_dir)
            self._remove_request_dir(request_dir)

    def _trim_by_disk_usage(self, dirs: list[Path]):
        """Remove oldest dirs first (dirs must already be sorted oldest-first) while
        disk usage remains at or above the configured threshold.
        """
        for request_dir in dirs:
            if self._disk_usage < self.task_settings.max_disk_percent_usage:
                break
            self._remove_request_dir(request_dir)

    def _clean_job_dirs(self):
        """Clean done/failed job request directories by age, size, and disk usage."""
        try:
            done_dirs = self._job_request_dirs('done_working_dir')
            failed_dirs = self._job_request_dirs('failed_working_dir')

            # condition 1: remove any done/failed request dir older than max_job_age_days
            max_age_seconds = self._days_to_seconds(self.task_settings.max_job_age_days)
            for request_dir in done_dirs + failed_dirs:
                if time.time() - request_dir.stat().st_mtime > max_age_seconds:
                    self._remove_request_dir(request_dir)
            done_dirs = [d for d in done_dirs if d.exists()]
            failed_dirs = [d for d in failed_dirs if d.exists()]

            # condition 2: cap the total size of done_working_dir
            self._trim_by_size(done_dirs, self.task_settings.max_done_working_dir_size_bytes)

            # condition 3: remove oldest done/failed request dirs while disk usage is over max
            remaining = sorted(
                (d for d in done_dirs + failed_dirs if d.exists()),
                key=lambda d: d.stat().st_mtime,
            )
            self._trim_by_disk_usage(remaining)
        except Exception as ex:
            app_exception(ex, 'failure=failed-cleaning-job-dirs')

    def _clean_batch_errors(self):
        """Clean batch errors: remove orphans and enforce cap."""
        try:
            job_ids = self.job_dao.get_all_job_ids()
            for batch_error in self.batch_error_dao.get_all(
                where={'request_id': where.not_(where.is_in(job_ids))}
            ):
                self.batch_error_dao.delete(batch_error)

            # Cap total batch errors to prevent unbounded growth. Read live off settings,
            # not task_settings — task_settings is a @cached_property and Cleaner is a
            # long-lived singleton, so baking a settings value in there would freeze it
            # at first access (same bug class as Scheduler.frequency).
            max_batch_errors = self.settings.app_settings.max_batch_errors
            for path in self.db.get_paths(BatchErrorModel, sort_order=SortOrder.DESC)[
                max_batch_errors:
            ]:
                try:
                    path.unlink(missing_ok=True)
                except OSError as ex:
                    app_exception(ex, f'failure=failed-capping-batch-error, path={path}')
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

        # clean done/failed job request directories
        self._clean_job_dirs()

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
            max_done_working_dir_size_bytes=15 * 1024 * 1024 * 1024,  # 15 GB
            max_job_age_days=28,
            max_jobs=500,
            max_ttl_batch_error=(60 * 60 * 24 * 90),  # 90 days
            max_notification_age_days=30,
        )
