"""Query Param Filter Pagination Model."""

from pydantic import Field, validator

from core.api.validation.models.query_param_filter_model import QueryParamFilterModel
from core.json_db import SortBy, SortOrder


class QueryParamFilterPaginationModel(QueryParamFilterModel):
    """Query Param Filter Pagination Model."""

    _not_unset_capable: list[str] = Field(
        default=[
            'by_alias',
            'exclude',
            'exclude_defaults',
            'exclude_none',
            'exclude_unset',
            'extra',
            'include',
            'limit',
            'offset',
            'sort',
            'sort_order',
        ]
    )

    limit: int = Field(50, ge=0, le=500)
    offset: int = Field(0, ge=0)
    sort: str | SortBy = Field('id', description='The field name used to sort the results.')
    sort_order: SortOrder = Field(SortOrder.ASC, description='The sort order: asc|desc.')

    @validator('sort', always=True)
    def _sort(cls, v):
        """Validate sort value."""
        match v.lower():
            case 'id' | 'index':
                return SortBy.INDEX
            case 'created':
                return SortBy.CREATED
            case 'modified':
                return SortBy.MODIFIED
            case _:
                return v

    @validator('sort_order', always=True)
    def _sort_order(cls, v):
        """Validate sort order."""
        match v:
            case SortOrder():
                return v
            case str():
                if v.lower() == 'asc':
                    v = SortOrder.ASC
                elif v.lower() == 'desc':
                    v = SortOrder.DESC
                else:
                    msg = f'Invalid sort order: {v}'
                    raise ValueError(msg)
            case _:
                msg = f'Invalid sort order: {v}'
                raise ValueError(msg)
        return v

    class Config:
        """Model Configuration."""

        validate_assignment = True
        validate_all = True
