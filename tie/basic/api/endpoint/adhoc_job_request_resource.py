"""Request Resource"""

from datetime import UTC, datetime, timedelta
from functools import cached_property

import falcon
from pydantic import Field, validator

from core.api.endpoint.endpoint_base_abc import EndpointBaseABC
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.dao.job_dao import JobRequestDAO
from core.model.model_base import ModelBase
from core.model.onboarding_model import is_onboarding_complete

from model.job_request_model import AdHocJobRequestModel  # isort:skip


class AdHocCreateRequest(ModelBase):
    """Request body model."""

    start_time: datetime = Field(None, description='')
    end_time: datetime = Field(None, description='')
    sample_types: list[str] = Field([], description='')

    @validator('sample_types')
    def validate_sample_types(cls, value):
        """Validate the sample types."""
        return [type_.lower().strip() for type_ in value]


class AdHocRequestResource(EndpointBaseABC):
    """Endpoint to cancel a request"""

    @cached_property
    def dao(self) -> JobRequestDAO:
        """Return the dao."""
        return JobRequestDAO(self.db, self.settings)

    def on_post(
        self,
        _req: FalconRequest,
        _: FalconResponse,
        body: AdHocCreateRequest,
    ):
        """Create an ad-hoc job request."""
        if not is_onboarding_complete(self.db):
            raise falcon.HTTPConflict(
                title='Onboarding Incomplete',
                description=(
                    'Setup is not finished — ad-hoc jobs cannot be queued until onboarding is '
                    'complete.'
                ),
            )
        return self._add_backfill_jobs(body)

    def _add_job(self, start_time, end_time, body: AdHocCreateRequest) -> dict:
        """Add the job to the database."""
        # TODO: All people would need to change this because of the settings structure change :-/
        job = AdHocJobRequestModel(
            date_queued=datetime.now(UTC),
            status=self.settings.job.status_pending,
            # additional_setting=body.additional_setting,
            start_time=start_time,
            end_time=end_time,
            sample_types=body.sample_types,
            pipeline='ingest',
        )
        self.dao.save(job)

        self.log.info(f'action=schedule-download, job={job.dict()}')

        return job.dict()

    def _add_backfill_jobs(self, body) -> list[dict]:
        """Add backfill jobs to the database."""
        start_time = body.start_time
        end_date = body.end_time
        backfill_frequency = timedelta(hours=self.settings.app_settings.backfill_frequency)
        jobs = []

        while start_time < end_date:
            end_time = min(start_time + backfill_frequency, end_date)
            jobs.append(self._add_job(start_time, end_time, body))
            start_time = end_time

        return jobs
