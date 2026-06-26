"""Class for /api/report/batch-error/export endpoint"""

import csv
import gzip
import json
from functools import cached_property
from io import BytesIO, StringIO
from typing import Literal

from pydantic import Field, validator
from spectree import Response

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_job
from core.api.validation.models import QueryParamFilterModel
from core.dao.batch_error_dao import BatchErrorDAO
from core.json_db import where
from core.model.tie import BatchErrorPaginatedResponseModel
from core.util.custom_handler import CustomHandler


class GetQueryParamModel(QueryParamFilterModel, where.ToWhere):
    """Params Model for batch error export.

    Inherits from QueryParamFilterModel which provides:
    - alias_generator = value_to_camel (auto camelCase aliases)
    - allow_population_by_field_name = True (accepts both snake_case and camelCase)
    """

    error_code: str | None = Field(None, description='Filter by error code.')
    request_id: str | None = Field(None, description='Filter by Request ID.')
    messages: list[str] | None = Field(None, description='Filter by messages.')
    reason: str | None = Field(None, description='Filter by reason.')
    format: Literal['csv', 'json'] = Field('json', description='Export format.')

    def to_where(self) -> where.WhereDict:
        """Convert the object to a where dictionary that can be passed to DAO objects."""
        return {
            'message': where.is_in(self.messages),
            'reason': where.contains(self.reason),
        }

    @validator('messages', always=True, pre=True)
    def _messages(cls, v):
        """Validate messages value."""
        match v:
            case str():
                return [f.strip() for f in v.split(',')]
            case _:
                return v


class BatchErrorExportResource(EndpointBase):
    """Class for /api/report/batch-error/export endpoint"""

    @cached_property
    def dao(self):
        """Return a new instance of the DAO."""
        return BatchErrorDAO(self.db)

    @spec.validate(
        query=GetQueryParamModel,
        resp=Response(HTTP_200=BatchErrorPaginatedResponseModel),
        skip_validation=True,
        tags=[tag_job],
    )
    def on_get(
        self,
        req: FalconRequest,  # noqa: ARG002
        resp: FalconResponse,
        query_params: GetQueryParamModel,
    ):
        """Return batch errors from job requests as a gzipped CSV or JSON file."""
        data = self.dao.get_all_for_query_params(
            query_params,
            request_id=query_params.request_id,
            error_code=query_params.error_code,
        )
        data = [d.dict() for d in data]
        resp.content_type = 'application/x-gzip'
        resp.set_header(
            'Content-Disposition',
            (
                'attachment; filename=batch_errors.csv.gz'
                if query_params.format == 'csv'
                else 'attachment; filename=batch_errors.json.gz'
            ),
        )
        resp.status = '200 OK'
        output = StringIO()
        if query_params.format == 'csv':
            if data:
                # Convert first item to dict to get fieldnames
                first_item = data[0]
                fieldnames = first_item.keys()

                writer = csv.DictWriter(output, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
                writer.writeheader()

                for item in data:
                    writer.writerow(item)
        else:
            output.write(json.dumps(data, cls=CustomHandler))

        gzip_buffer = BytesIO()
        with gzip.GzipFile(mode='wb', fileobj=gzip_buffer) as gz_file:
            gz_file.write(output.getvalue().encode('utf-8'))

        resp.data = gzip_buffer.getvalue()
        resp.content_length = len(resp.data)
