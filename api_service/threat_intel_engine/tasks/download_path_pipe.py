"""Task Module"""
# standard library
from typing import TYPE_CHECKING

# third-party
from tcex.backports import cached_property

# first-party
from model.job_request_model import JobRequestModel
from more import Metrics, session
from schema import JobRequestSchema
from tasks.model import TaskSettingPipeModel
from tasks.task_path_pipe_abc import TaskPathPipeABC
from tasks.tasks import Tasks

if TYPE_CHECKING:
    # standard library
    from pathlib import Path

    # third-party
    from pydantic import BaseModel
    from tcex import TcEx


class DownloadPathPipe(TaskPathPipeABC):
    """Task Path Pipe Module

    Task Flow:

    1. launch_preflight_checks - run pre-flight checks before launching task (run method)
    2. launch - launch task, typically as multiprocessing.Process
    3. run - task entry point

    The download task gets "jobs" from the job request table, which is populated by the schedule
    next download task. This task writes output data to the working directory of the next
    task. The directory structure is automatically handled by the TaskPathPipeABC class and the
    add_task_path_pipe method in tasks.py (called from app.py).

    """

    def __init__(self, settings: 'BaseModel', tcex: 'TcEx', provider_sdk: any):
        """Initialize class properties."""
        super().__init__(settings, tcex)

        # properties
        self.log = tcex.log
        self.metrics = Metrics()
        self.provider_sdk = provider_sdk

    def _process_counts(self, request_id: str, counts: dict):
        """Report metrics to the metrics table and counts to the job request table."""

        # update the metrics date for TI type count. this data is used to populate the dashboard
        for count_name, count_value in counts.items():
            self.metrics.process_metric(count_name, count_value)

        # consolidate group and indicator counts to update the job request table. these values
        # are helpful to compare against the upload counts to ensure all data was uploaded

        # everything left over is an indicator type
        count_indicator = sum(counts.values())

        # update the job request table with the counts
        self._db_increment_counts(
            request_id,
            {
                'count_download_indicator': count_indicator,
            },
        )

    def _throttle_download(self) -> bool:
        """Throttle download to prevent too much stale data on disk.

        There are currently two types of tasks: scheduled and ad-hoc. Scheduled tasks are given
        higher priority so that new Threat Intel is processed as soon as possible. Ad-hoc tasks
        are given lower priority so that the system can catch up on scheduled tasks.

        Because it is possible for ad-hoc tasks to pull the same data as a scheduled task, we
        want to ensure that the ad-hoc data is downloaded as close to the processing of the data
        as possible. The less time between the download and processing, the less likely the data
        will be duplicated.
        """

        # the possible statuses that would NOT block a download task
        throttle_statutes = [
            self.settings.status_cancelled,
            self.settings.status_failed,
            self.settings.status_pending,
        ]
        # the Tasks.status_final is a list of all final statuses calculated in the tasks.py
        throttle_statutes.extend(Tasks.status_final)

        query = session.query(JobRequestSchema).filter(
            JobRequestSchema.status.not_in(throttle_statutes)
        )
        count = self.db.get_record(query, 'count', 'Unexpected error getting job count.')
        self.log.trace(
            f'task-event=throttle-download, count={count}, final-status={Tasks.status_final}'
        )

        # block download if the count is greater than the throttle limit
        if count >= self.settings.throttle_limit:
            return True
        return False

    def launch_preflight_checks(self):
        """Run pre-flight check before launching task.

        This method checks to see if the download task should be launched. The download task
        depends on available jobs in the job request table. If there are no jobs in the table
        that are in the "pending" state or if the throttle limit has been reached, then the this
        task will not be launched.
        """
        if self._throttle_download():
            self.log.trace(
                f'task-event=launch-preflight-check-skip, action={self.task_settings.name}, '
                f'reason=throttle-limit-hit, throttle-limit={self.settings.throttle_limit}'
            )
            return

        # process "scheduled" tasks first, then ad-hoc request,
        # and finally by the date the job request was queued
        query = (
            session.query(JobRequestSchema)
            .filter(
                (JobRequestSchema.status == self.settings.status_pending)
                | (JobRequestSchema.status == self.task_settings.status_active)
            )
            # order by job type desc (scheduled, then ad-hoc)
            .order_by(JobRequestSchema.job_type.desc(), JobRequestSchema.date_queued.asc())
            .limit(1)
        )
        last_download: JobRequestSchema = self.db.get_record(
            query, 'one_or_none', 'Unexpected error getting last download.'
        )

        if last_download is not None:
            self.log.info(
                f'task-event-path-pipe=launch-preflight-checks, '
                f'task-name={self.task_settings.name}, request_id={last_download.request_id}'
            )
            priority = 'low' if last_download.job_type == 'ad-hoc' else 'high'
            self.launch(last_download.request_id, priority=priority)
        else:
            self.log.trace(
                f'task-event=launch-preflight-check-skip, action={self.task_settings.name}, '
                f'reason=no-pending-job-request-found'
            )

    def run(self, request_id: str, _: 'Path', output_dir: 'Path'):
        """Run the task.

        The request_id, input_dir, and output_dir are passed to the run method of all task. For
        the download task input comes from the job request table and therefore the input_dir is
        not used. The output_dir is used to write the downloaded data to disk and is the input
        directory for the next task in the pipe.
        """
        # looking up the record here in the forked process, to ensure
        # no conflicts with the orm model when we update the record later
        request = JobRequestModel.from_orm(self._db_get_request_by_id(request_id))

        # Example Filter Definition:
        # for this example, we will assume that the remote API accepts start and end dates, as well
        # as a TQL query and owner
        last_modified_filter_start = self.tcex.utils.any_to_datetime(
            request.last_modified_filter_start).strftime('%Y-%m-%d %H:%M:%S')
        last_modified_filter_end = self.tcex.utils.any_to_datetime(
            request.last_modified_filter_end).strftime('%Y-%m-%d %H:%M:%S')

        tql = f'{self.settings.tql} AND lastModified GEQ "{last_modified_filter_start}" ' \
              f'AND lastModified LT "{last_modified_filter_end}"'

        # collect the counts of all the TI types to be written as count in job
        # request table  and metrics for the dashboard in the metrics table
        ti_type_counts = {}
        indicators = []
        for indicator in self.provider_sdk.get_all(tql, self.settings.external_owner):
            indicators.append(indicator)
            ti_type = indicator.get('type')
            if ti_type in ti_type_counts:
                ti_type_counts[ti_type] += 1
            else:
                ti_type_counts[ti_type] = 1

        # use built-in method to write the data to disk, this method also updates heartbeat
        self._write_results(indicators, output_dir, 'indicators')

        # update job request counts and dashboard metrics
        self._process_counts(request_id, ti_type_counts)

    @cached_property
    def task_settings(self) -> 'TaskSettingPipeModel':  # pylint: disable=no-self-use
        """Return the task settings.

        Tasks have standard model that is used to define the task settings. This method returns
        the settings model for the download task. Any additional settings can be defined in this
        property.

        The start and end date fields in the database are defined here and are automatically updated
        by the task manager when the task is started and completed.
        """

        return TaskSettingPipeModel(
            base_path=self.settings.base_path,
            date_field_start=JobRequestSchema.date_download_start,
            date_field_complete=JobRequestSchema.date_download_complete,
            description='Downloads the threat intel data from provider API.',
            max_execution_minutes=20,
            name='Download',
        )
