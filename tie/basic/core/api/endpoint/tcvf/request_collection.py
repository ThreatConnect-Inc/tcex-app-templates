"""Class for /api/1.0/job/request endpoint"""

# standard library

# standard library
import re
from functools import cached_property

# third-party
from pydantic import validator
from spectree import Response

# first-party
from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_job
from core.api.validation.models.query_param_filter_pagination_model import (
    QueryParamFilterPaginationModel,
)
from core.dao.job_dao import JobRequestDAO
from core.json_db import SortBy, where
from model.job_request_model import JobRequestPaginatedResponseModel


class GetQueryParamModel(QueryParamFilterPaginationModel):
    """Params Model"""

    @property
    def extra_fields(self):
        """The extra fields that are not part of the base model."""
        return {key: value for key, value in self.__dict__.items() if key not in self.__fields__}

    @validator('sort', always=True)
    def _sort(cls, v):  # noqa: N805
        """Validate sort value."""
        # because BatchErrorModel uses the default default_factory for Index(),
        # it's ID is a UUID7, which means it is time sortable by INDEX.
        # because of that, we can use INDEX when the sort is CREATED.
        match v.lower():
            case 'id' | 'index':
                return SortBy.INDEX
            case 'created':
                return SortBy.INDEX
            case 'modified':
                return SortBy.MODIFIED
            case _:
                return v

    def camel_to_snake(self, camel_str: str) -> str:
        """Convert a camelCase string to snake_case."""
        # Insert an underscore before each uppercase letter (not at the start) and lowercase it
        snake_str = re.sub(r'(?<!^)(?=[A-Z])', '_', camel_str).lower()
        return snake_str

    @property
    def transformed_params(self):
        """The transformed params."""
        transformed_params = {}
        for key, value in self.extra_fields.items():
            key = self.camel_to_snake(key)
            transformed_params[key] = value
        return transformed_params

    def to_where(self) -> where.WhereDict:
        """Convert the object to a where dictionary that can be passed to DAO objects."""
        where_dict = {}
        # iterate over all of the properties of the base model
        for key, value in self.transformed_params.items():
            # if the value is not None, add it to the where dictionary
            if not value:
                continue
            if isinstance(value, str):
                where_dict[key] = where.contains(value)
            elif isinstance(value, list):
                where_dict[key] = where.is_in(value)
            else:
                pass
                # print(f'Unknown type for {key}: {value}')
        return where_dict

    class Config:  # type: ignore
        """Model Configuration."""

        extra = 'allow'
        validate_assignment = True
        validate_all = True


# pylint: disable=unused-argument
class RequestCollectionResource(EndpointBase):
    """Class for /api/1.0/job/request endpoint"""

    @cached_property
    def dao(self) -> JobRequestDAO:
        """Return the dao."""
        return JobRequestDAO(self.db, self.settings)

    @spec.validate(
        query=GetQueryParamModel,
        resp=Response(HTTP_200=JobRequestPaginatedResponseModel),
        skip_validation=True,
        tags=[tag_job],
    )
    def on_get(
        self,
        _req: FalconRequest,
        resp: FalconResponse,
        query_params: GetQueryParamModel,
    ):
        """Get job request data."""
        resp_data = self.dao.get_page_for_query_params(query_params)
        resp.media = resp.response_model(resp_data, JobRequestPaginatedResponseModel, query_params)
