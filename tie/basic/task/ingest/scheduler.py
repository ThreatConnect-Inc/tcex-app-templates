"""Batch Submit"""

from datetime import UTC, datetime, timedelta
from functools import cached_property

from core.model.onboarding_model import is_onboarding_complete
from core.model.tie.task_setting_model import TaskSettingModel
from core.task.task_abc import TaskABC
from model import JobRequestModel


class Scheduler(TaskABC):
    """Process to submit JSON files to TC batch API."""

    def __init__(self, settings, tcex, db, *, pipeline=None):
        """Initialize Class Properties."""
        super().__init__(settings, tcex, db)
        self.pipeline = pipeline

    @property
    def backfill(self) -> timedelta:
        """Return how far back the first scheduled run reaches.

        A property, not a cached value, for the same reason as `frequency` below: this
        moved onto `app_settings` and is now editable from the Settings UI, so caching it
        in __init__ would pin the boot-time value on this long-lived singleton.
        """
        return timedelta(hours=self.settings.app_settings.backfill)

    @property
    def backfill_frequency(self) -> timedelta:
        """Return the chunk size a scheduled time range is split into. Read live."""
        return timedelta(hours=self.settings.app_settings.backfill_frequency)

    @property
    def frequency(self) -> timedelta:
        """Return how often a new scheduled job is created.

        Read fresh on every access rather than cached in __init__. A settings save
        rebinds settings.app_settings (core/api/endpoint/tcvf/settings_resource.py),
        so reading it here means a Poll Frequency change from the Settings UI takes
        effect on the next tick instead of requiring an app restart. Scheduler is a
        long-lived singleton, so caching this would pin the boot-time value forever.
        """
        return timedelta(hours=self.settings.app_settings.frequency)

    def launch_preflight_checks(self):
        """Run pre-flight check before launching task."""
        self.launch()

    def launch(self):
        """Launch the task."""
        self.run()

    def run(self):
        """Schedule next download."""
        self.log.info(f'event=schedule-download, action=running-task, pipeline={self.pipeline}')

        # Do not queue ingestion work until an admin has completed onboarding -- until then
        # the settings the download task depends on (credentials, selections) are still at
        # their seeded defaults, so any job scheduled here would fail or pull the wrong data.
        if not is_onboarding_complete(self.db):
            self.log.info(
                'task-event=schedule-download, action=skip-schedule, reason=onboarding-incomplete'
            )
            return

        most_recent_scheduled_job = self.job_dao.get_most_recent_scheduled_job(
            pipeline=self.pipeline
        )
        now = datetime.now(UTC)

        if not most_recent_scheduled_job:
            self.tcex.log.info('task-event=schedule-download, action=schedule-backfill-downloads')
            start_time = now - self.backfill
            self._add_backfill_jobs(start_time, now)
            return

        end_time = most_recent_scheduled_job.end_time
        self.tcex.log.info(
            'task-event=schedule-download, '
            f'end_time={end_time}, '
            f'now={now}, '
            f'frequency={self.frequency}'
        )

        if (now - end_time) < self.frequency:
            self.tcex.log.info('task-event=schedule-download, action=skip-schedule')
            return

        self._add_backfill_jobs(end_time, now)

    def _add_backfill_jobs(self, start_time: datetime, end_date: datetime):
        """Add backfill jobs to the database."""
        while start_time < end_date:
            end_time = min(start_time + self.backfill_frequency, end_date)
            self._add_job(start_time, end_time)
            start_time = end_time

    def _add_job(self, start_time: datetime, end_time: datetime):
        """Add the job to the database."""
        self.tcex.log.info(f'action=add-job, start_time={start_time}, end_time={end_time}')
        job = JobRequestModel(
            date_queued=datetime.now(UTC),
            status=self.settings.job.status_pending,
            # Add custom job request model fields here
            start_time=start_time,
            end_time=end_time,
            # Lowercased so a scheduled job records the same case as an ad-hoc one —
            # `AdHocCreateRequest.validate_sample_types` lowercases what the form posts,
            # while the settings record can hold catalogue case ('Event'). Normalising
            # here means anything reading `request.sample_types` sees one casing whichever
            # way the job was created.
            sample_types=sorted(
                {str(entry).strip().lower() for entry in self.settings.app_settings.sample_types}
            ),
        )
        if self.pipeline:
            job.pipeline = self.pipeline
        self.job_dao.save(job)

        self.tcex.log.info(f'action=schedule-download, job={job.dict()}')

    @cached_property
    def task_settings(self) -> TaskSettingModel:
        """Return the task settings."""
        return TaskSettingModel(
            description='Schedules the next download.',
            max_execution_minutes=10,
            name='Schedule Downloads',
            schedule_period=5,
            schedule_unit='seconds',
        )
