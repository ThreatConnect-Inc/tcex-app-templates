"""Batch Submit"""
# standard library
from datetime import timedelta
from typing import Optional
from uuid import uuid4

# third-party
import arrow
from model import JobRequestModel
from schema import JobRequestSchema
from tasks.model import TaskSettingModel
from tasks.task_abc import TaskABC
from tcex.backports import cached_property


class ScheduleNextDownload(TaskABC):
    """Task Module

    Task Flow:

    1. launch_preflight_checks - run pre-flight checks before launching task (run method)
    2. launch - launch task, typically as multiprocessing.Process
    3. run - task entry point

    The schedule next download task creates DB entries (job request) for the download task. The job
    request will be created with a start and end date. The start date will be the end date of the
    previous download task. The end date will be the start date + the configured interval. The
    interval is configured in the settings model.
    """

    def _add_job(
        self,
        start_date: 'arrow.Arrow',
        end_date: 'arrow.Arrow',
    ):
        """Add the job to the database."""
        request_data = {
            'request_id': str(uuid4()),
            'job_type': 'scheduled',
            'status': 'pending',
            'last_modified_filter_start': start_date,
            'last_modified_filter_end': end_date,
        }

        # create the job request and update db
        record = self.db.create_record(
            JobRequestSchema,
            request_data,
            'Unexpected error creating scheduled download request.',
        )
        self.db.add_record(
            self.session, record, 'Unexpected error adding scheduled download request.'
        )
        self.tcex.log.info(
            f'action=schedule-next-download, '
            f'last_modified_filter_start={start_date}, '
            f'last_modified_filter_end={end_date}'
        )

    def _add_job_backfill(self, last_download_time: 'arrow.Arrow'):
        """Add one or more jobs with backfill time window."""
        range_end = arrow.utcnow().shift(hours=-1)

        for start, end in self.tcex.utils.chunk_date_range(
            last_download_time, range_end, self.settings.time_chunk_size_hours_backfill, 'hours'
        ):
            self._add_job(start, end)

    def _add_job_standard(self, last_download_time: 'arrow.Arrow'):
        """Add a job with standard time window."""
        start_date = last_download_time
        end_date = last_download_time.shift(hours=+self.settings.time_chunk_size_hours)
        self._add_job(start_date, end_date)

    def _get_job(self) -> Optional[JobRequestModel]:
        """Return the newest job if there is one."""
        query = (
            self.session.query(JobRequestSchema)
            .filter(JobRequestSchema.job_type == 'scheduled')
            .order_by(JobRequestSchema.date_queued.desc())
            .limit(1)
        )
        return self.db.get_record(query, 'one_or_none', 'Unexpected error getting last download.')

    def _get_last_download_time(
        self, last_download: Optional[JobRequestSchema] = None
    ) -> Optional['arrow.Arrow']:
        """Get the last download time from the DB or use the initial backfill time."""
        last_download_time = arrow.utcnow().shift(days=-self.settings.initial_backfill_days)
        if last_download is not None:
            last_download_time = last_download.last_modified_filter_end
        return last_download_time

    def launch(self, last_download_time: 'arrow.Arrow'):  # pylint: disable=arguments-differ
        """Launch the task."""
        self.run(last_download_time)

    def launch_preflight_checks(self):
        """Run pre-flight check before launching task."""
        last_download = self._get_job()

        # get last download time
        last_download_time = self._get_last_download_time(last_download)

        # last download time should never get ahead of "now", and should be at least 2 hours ago
        now = arrow.utcnow()
        if last_download_time < now and now - last_download_time > timedelta(hours=2):
            self.log.info(f'task-event=launch-preflight-check, action={self.task_settings.name}')
            self.launch(last_download_time)
        else:
            self.log.trace(
                f'task-event=launch-preflight-check-skip, action={self.task_settings.name}, '
                f'last-download-time={last_download_time}, now={now}, '
                f'reason=last-download-less-than-2-hours-ago, delta={now - last_download_time}'
            )

    def run(self, last_download_time: 'arrow.Arrow'):
        """Schedule next download."""
        self.tcex.log.trace(f'task-event=run, action={self.task_settings.slug}')

        # if the last download time is less than the configured time chunk
        # size, then add a standard job, otherwise add a backfill job
        if arrow.utcnow() - last_download_time < timedelta(
            hours=self.settings.time_chunk_size_hours_backfill
        ):
            self._add_job_standard(last_download_time)
        else:
            self._add_job_backfill(last_download_time)

    @cached_property
    def task_settings(self) -> 'TaskSettingModel':
        """Return the task settings.

        Tasks have standard model that is used to define the task settings. This method returns
        the settings model for the download task. Any additional settings can be defined in this
        property.
        """

        return TaskSettingModel(
            description='Schedules the next threat intel downloads.',
            max_execution_minutes=10,
            name='Schedule Downloads',
            schedule_period=10,
            schedule_unit='seconds',
        )
