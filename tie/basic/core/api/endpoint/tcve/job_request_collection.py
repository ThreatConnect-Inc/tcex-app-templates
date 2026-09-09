"""Job request collection resource for /api/job/request endpoint."""

# standard library
from datetime import UTC, datetime
from uuid import uuid4

# third-party
import arrow
import falcon
from pydantic import BaseModel, Field, ValidationError, validator
from tcex.util import Util

# first-party
from core.api.endpoint.endpoint_base_abc import EndpointBaseABC
from core.json_db import SortBy, SortOrder
from model.job_request_model import (
    AdHocJobRequestModel,
    JobRequestModel,
    JobRequestPaginatedResponseModel,
)


class PostBodyModel(BaseModel, arbitrary_types_allowed=True):
    """Request body model for ad-hoc job creation."""

    range_start: arrow.Arrow = Field(alias='rangeStart')
    range_end: arrow.Arrow = Field(alias='rangeEnd')

    @validator('range_start', 'range_end', pre=True)
    def validate_time_input(cls, value: str) -> 'arrow.Arrow':
        """Validate time input. All date inputs are assumed to be in UTC."""
        return Util().any_to_datetime(value, 'UTC')


class JobRequestCollection(EndpointBaseABC):
    """Class for /api/job/request endpoint."""

    def on_get(self, req: falcon.Request, resp: falcon.Response):
        """Handle GET requests — return paginated, filtered job records."""
        by_alias = req.get_param_as_bool('by_alias', default=False)
        request_id = req.get_param('request_id')
        job_type = req.get_param('job_type')
        status_csv = req.get_param('status')
        status_list = [s.strip() for s in status_csv.split(',')] if status_csv else None

        offset = int(req.get_param('offset') or 0)
        limit = int(req.get_param('limit') or 50)
        sort_order_raw = (req.get_param('sort_order') or 'desc').lower()
        sort_order = SortOrder.DESC if sort_order_raw == 'desc' else SortOrder.ASC

        def _where(r: JobRequestModel) -> bool:
            if job_type is not None and r.job_type.lower() != job_type.lower():
                return False
            if request_id is not None and request_id.lower() not in r.request_id.lower():
                return False
            if status_list and r.status.lower() not in [s.lower() for s in status_list]:
                return False
            return True

        records = list(
            self.db.load_all(
                JobRequestModel,
                where=_where,
                sort_by=SortBy.CREATED,
                sort_order=sort_order,
            )
        )

        total_count = len(records)
        page = records[offset : offset + limit]

        # JobRequestModel inherits orm_mode = True from JobRequestBaseModel.Config.
        data = [JobRequestModel.from_orm(r) for r in page]

        response = JobRequestPaginatedResponseModel(
            data=data,
            count=len(data),
            total_count=total_count,
        )
        resp.media = response.dict(by_alias=by_alias, exclude_none=True)

    def on_post(self, req: falcon.Request, resp: falcon.Response):
        """Handle POST requests — create ad-hoc job records for the given date range."""
        try:
            body = PostBodyModel.parse_obj(req.media or {})
        except ValidationError as ex:
            # Every sibling endpoint wraps this; unwrapped, a malformed body escaped as a
            # 500 instead of telling the caller what was wrong with their request.
            raise falcon.HTTPBadRequest(description=str(ex)) from ex
        self.log.debug(f'body={body}')

        response_media = []
        for start, end in self.tcex.util.chunk_date_range(
            body.range_start,
            body.range_end,
            self.settings.time_chunk_size_hours_backfill,
            'hours',
        ):
            request_id = str(uuid4())
            record = AdHocJobRequestModel(
                request_id=request_id,
                status=self.settings.job.status_pending,
                date_queued=datetime.now(UTC),
                pipeline='egress',
                last_modified_filter_start=start.isoformat() if start else None,
                last_modified_filter_end=end.isoformat() if end else None,
                tql_config_version='',
            )
            self.db.save(record)
            response_media.append(
                {
                    'request_id': record.request_id,
                    'job_type': record.job_type,
                    'status': record.status,
                    'last_modified_filter_start': record.last_modified_filter_start,
                    'last_modified_filter_end': record.last_modified_filter_end,
                }
            )
        resp.media = response_media
