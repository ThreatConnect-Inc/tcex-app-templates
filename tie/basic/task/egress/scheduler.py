"""Batch Submit"""

# standard library
from datetime import UTC, datetime, timedelta
from functools import cached_property

# first-party
from core.model.tie.task_setting_model import TaskSettingModel
from core.task.task_abc import TaskABC
from model import JobRequestModel


class Scheduler(TaskABC):
    """Scheduler Task."""

    def __init__(self, settings, tcex, db, *, pipeline=None):
        """Initialize Class Properties."""
        super().__init__(settings, tcex, db)
        self.pipeline = pipeline

        self.backfill = timedelta(hours=settings.advanced_settings.backfill)
        self.backfill_frequency = timedelta(hours=settings.advanced_settings.backfill_frequency)
        self.frequency = timedelta(hours=settings.advanced_settings.frequency)

    def launch_preflight_checks(self):
        """Run pre-flight check before launching task."""
        self.launch()

    def launch(self):  # pylint: disable=arguments-differ
        """Launch the task."""
        self.run()

    def _add_job(self, start_time, end_time):
        """Add the job to the database."""
        job = JobRequestModel(
            date_queued=datetime.now(UTC),
            status=self.settings.job.status_pending,
            # Add custom job request model fields here
            start_time=start_time,
            end_time=end_time,
        )
        if self.pipeline:
            job.pipeline = self.pipeline

        self.job_dao.save(job)

        self.tcex.log.info(f'action=schedule-download, job={job.dict()}')

    def _add_backfill_jobs(self, end_date: datetime):
        """Add backfill jobs to the database."""
        start_time = end_date - self.backfill
        while start_time < end_date:
            end_time = min(start_time + self.backfill_frequency, end_date)
            self._add_job(start_time, end_time)
            start_time = end_time

    def run(self):
        """Run the task."""
        self.log.info(f'event=schedule-download, action=running-task, pipeline={self.pipeline}')
        most_recent_job = self.job_dao.get_most_recent_scheduled_job(pipeline=self.pipeline)
        now = datetime.now(UTC)

        if not most_recent_job:
            self.log.info('event=not-scheduling-requests, reason=no-existing-jobs')
            self._add_backfill_jobs(now)
            return

        # TODO: This check is not present in the ingest scheduler,
        # can we remove it in the egress one?
        if most_recent_job.status not in [self.settings.job.status_failed, 'upload complete']:
            return

        end_time = most_recent_job.end_time
        if (now - end_time) < self.frequency:
            self.log.info('event=not-scheduling-requests, reason=too-soon')

        # TODO: Previous tcve scheduler checked if the last job succeeded or failed. If it failed,
        # it would use the start time of the last job as the start time for the new job.
        while (now - end_time) > self.frequency:
            self.tcex.log.info('task-event=schedule-download, action=schedule-next-download')
            self._add_job(end_time, end_time + self.frequency)
            end_time += self.frequency

    @cached_property
    def task_settings(self) -> TaskSettingModel:
        """Return the task settings.

        Tasks have standard model that is used to define the task settings. This method returns
        the settings model for the download task. Any additional settings can be defined in this
        property.
        """
        return TaskSettingModel(
            description='Schedules the next threat intel downloads.',
            max_execution_minutes=10,
            name='Schedule Downloads',
            schedule_period=5,
            schedule_unit='seconds',
        )
