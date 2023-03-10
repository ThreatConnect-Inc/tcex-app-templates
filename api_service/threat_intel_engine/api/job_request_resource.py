"""Class for /api/1.0/job/request endpoint"""
# standard library
from typing import List, Optional
from uuid import uuid4

# third-party
import arrow
import falcon
from api.resource_abc import ResourceABC
from model import FilterParamPaginatedModel, JobRequestModel
from pydantic import BaseModel, Field, validator
from schema import JobRequestSchema
from sqlalchemy import func
from sqlalchemy.orm import Query
from tcex.utils import Utils


class GetQueryParamModel(FilterParamPaginatedModel):
    """Params Model"""

    job_type: Optional[str] = Field(None, description='Filter by Job Type.')
    request_id: Optional[str] = Field(None, description='Filter by Request ID.')
    status: Optional[str] = Field(None, description='Filter by Status.')


class PostBodyModel(BaseModel, arbitrary_types_allowed=True):
    """Request body model."""

    range_start: arrow.Arrow = Field(alias='rangeStart')
    range_end: arrow.Arrow = Field(alias='rangeEnd')

    # pylint: disable=no-self-argument,
    @validator('range_start', 'range_end', pre=True)
    def validate_time_input(cls, value: str) -> 'arrow.Arrow':
        """Validate time input.

        All date inputs are assumed to be in UTC.
        """
        return Utils().any_to_datetime(value, 'UTC')


# pylint: disable=unused-argument
class JobRequestResource(ResourceABC):
    """Class for /api/1.0/job/request endpoint"""

    validation_models = {
        'GET': {
            'request': {
                'query_params': GetQueryParamModel,
            }
        },
        'POST': {
            'request': {
                'body': PostBodyModel,
            }
        },
    }

    def _db_query_get(
        self,
        job_type: Optional[str],
        request_id: Optional[str],
        status: Optional[str],
    ) -> Query:
        """Return DB query."""
        query = self.session.query(JobRequestSchema)

        # filter on job type
        if job_type is not None:
            query = query.filter(func.lower(JobRequestSchema.job_type) == job_type.lower())

        # filter on request id
        if request_id is not None:
            query = query.filter(JobRequestSchema.request_id.ilike(f'%{request_id}%'))

        # filter on status
        if status is not None:
            query = query.filter(func.lower(JobRequestSchema.status) == status.lower())

        return query

    def _db_result_get(self, query: Query) -> List[JobRequestSchema]:
        """Return DB records."""
        return self._db_get_record(
            query, 'all', 'Unexpected error occurred while retrieving Job Requests.'
        )

    def on_get(self, req: falcon.Request, resp: falcon.Response):
        """Handle GET requests."""
        query = self._db_query_get(
            req.context.params.job_type, req.context.params.request_id, req.context.params.status
        )

        # paginator
        sort = self._db_sort(req.context.params, JobRequestSchema, default_sort='request_id')
        paginator = self._db_paginator(query, req, sort)

        # generate and return the response
        resp.media = self.response_media(
            req,
            self._db_result_get(paginator.query),
            JobRequestModel,
            req.context.params,
            paginator,
        )

    def on_post(self, req: 'falcon.Request', resp: 'falcon.Response'):
        """Handle GET requests."""
        self.log.debug(f'body={req.context.body}')
        response_media = []
        for start, end in self.tcex.utils.chunk_date_range(
            req.context.body.range_start,
            req.context.body.range_end,
            self.settings.time_chunk_size_hours_backfill,
            'hours',
        ):
            # self.log.debug(f'start={start}')
            # self.log.debug(f'end={end}')
            uuid = str(uuid4())

            record_data = {
                'request_id': uuid,
                'job_type': 'ad-hoc',
                'status': 'pending',
                'last_modified_filter_start': start,
                'last_modified_filter_end': end,
            }
            record = self._db_create_record(
                JobRequestSchema,
                record_data,
                'Unexpected error creating ad-hoc download request.',
            )
            self._db_add_record(record, 'Unexpected error adding ad-hoc download request.')
            response_media.append(record_data)
        resp.media = response_media
