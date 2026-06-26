"""Query Param Filter Model."""

import logging
import re
from typing import Any

from pydantic import Field, validator

from core.api.validation.models.query_param_model import (
    QueryParamModel,
    param_to_list,
    values_to_snake,
)
from core.json_db.where import ToWhere, WhereDict

# get primary API logger
logger = logging.getLogger('tcex')


class ParamModelFilter:
    """Query Param Filter Model.

    Convert multiple or single params to Pydantic include/exclude filter.

    https://docs.pydantic.dev/latest/usage/serialization/#advanced-include-and-exclude

    Example:
    * 'one,two,three.a' -> {'one': True, 'two': True, 'three': {'a'}}
    * ['one,two', 'three'] -> {'one': True, 'two': True, 'three': True}
    * ['one', 'two', 'three.a.b.c'])) -> {'one': True, 'two': True, 'three': {'a': {'b': {'c'}}}}
    * ['one', 'two', 'three.a|b|c'])) -> {'one': True, 'two': True, 'three': {'a', 'c', 'b'}}
    * ['one', 'two', 'three.a.b.c', 'three.a.b.d', 'three.a.f'])) ->
        {'one': True, 'two': True, 'three': {'a': {'b': {'c', 'd'}, 'f': True}}}
    """

    def __init__(self) -> None:
        """Initialize instance properties."""
        self.array_pattern = r'(?P<field>.*)(?P<array>\[(?P<index>.*)\])'
        self.nested_key_delimiter = '|'  # delimiter for multiple nested keys
        self.param_delimiter = ','  # delimiter for multiple params in a single query param
        self.path_delimiter = ''  # delimiter for path keys

    def _field_array(self, array_data: re.Match, field_filters: dict[str, Any], parts: list[str]):
        """Process filter fields that are formatted for array (e.g., child[0].id)."""
        field = array_data.group('field')
        index = array_data.group('index')
        index = '__all__' if index == '' else int(index)

        if self._is_processed(field, field_filters):
            # handle non array pattern (the field has been processed, no filters can be added)
            # input: (child) -> output: {'child': True}
            pass
        elif len(parts) == 1:
            # handle simple single array value input pattern
            # input: (child[]) -> output: {'child': {'__all__': True}}
            field_filters[field] = {index: True}
        else:
            # handle multiple level array patterns
            # input: (child[].id) -> output: {'child': {'__all__': {'id': True}}}
            # input: (child[0].id) -> output: {'child': {0: {'id': True}}}
            # input: (child[-1].id|name) -> output: {'child': {-1: {'id': True, 'name': True}}}
            # input: (child[].home.id) -> output: {'child': {'__all__': {'home': {'id': True}}}}
            parts[0] = field  # replace field[] with field
            parts.insert(1, str(index))  # add index into the dict
            field_filters.setdefault(parts[0], {})
            self._nested(parts[1:], field_filters[parts[0]])

    def _is_processed(self, field: str, field_filters: dict[str, Any]) -> bool:
        """Return True if the field has already been processed (included/exclude)."""
        return field in field_filters and field_filters.get(field) is True
        # return field_filters.get(field) and field_filters.get(field) is True  # type: ignore

    def _nested(self, parts: list[str], field_filters: dict[str, Any]):
        """Process nested path and key values."""
        # searching for expression for arrays (e.g. child[0].id)
        array_data = re.search(self.array_pattern, str(parts[0]))
        if array_data and array_data.group('array'):
            # handle array pattern
            self._field_array(array_data, field_filters, parts)
        # elif len(parts) == 0:
        #     return
        elif len(parts) == 1:
            # handle simple singe value input pattern
            # input: (id) -> output: {'id': True}
            field_filters[parts[0]] = True
        elif len(parts) == 2:
            field_filters.setdefault(parts[0], {})
            if self._is_processed(parts[0], field_filters):
                pass
            elif self.nested_key_delimiter in parts[1]:
                # handle multiple level patterns, with multiple keys
                # input: (one.a|b) -> output: {'one': {'a': True, 'b': True}}
                for nested_key in parts[1].split(self.nested_key_delimiter):
                    field_filters[parts[0]].update({nested_key: True})
            else:
                # handle multiple level patterns
                # input: (one.a) -> output: {'one': {'a': True}}
                # input: (one.a, one.b) -> output: {'one': {'a': True, 'b': True}}
                field_filters[parts[0]].update({parts[1]: True})
        else:
            # handle multiple level patterns
            # input: (one.a.b|c) -> output: {'one': {'a': {'b': True, 'c': True}}}
            field_filters.setdefault(parts[0], {})
            self._nested(parts[1:], field_filters[parts[0]])

    def _normalize_data(self, filter_data: list[str] | str) -> list[str]:
        """Normalize the input data."""
        return [
            v.strip() for raw_value in filter_data for v in raw_value.split(self.param_delimiter)
        ]

    def generate_params(self, filter_data: list[str] | str | None) -> dict[str, Any] | None:
        """Generate the params from input data."""
        if filter_data is None:
            return filter_data

        field_filters = {}
        for filter_ in self._normalize_data(filter_data):
            self._nested(filter_.split(self.path_delimiter), field_filters)
        return field_filters


class QueryParamFilterModel(QueryParamModel, ToWhere):
    """Model and validation for on_get() method."""

    _not_unset_capable: list[str] = Field(
        default=[
            'by_alias',
            'exclude',
            'exclude_defaults',
            'exclude_none',
            'exclude_unset',
            'include',
        ],
        description='Fields that are not unset capable.',
    )

    exclude: list[str] | None = Field(
        None, description='One or more fields to exclude from response.'
    )
    exclude_defaults: bool = Field(
        False,
        alias='excludeDefaults',
        description='Exclude any field that has a default value.',
    )
    exclude_none: bool = Field(
        True,
        alias='excludeNone',
        description='Exclude any field that has a null value.',
    )
    exclude_unset: bool = Field(
        True,
        alias='excludeUnset',
        description='Exclude any field that was not explicitly set.',
    )
    include: list[str] | None = Field(
        None,
        description='One or more fields to include in response (alias for include).',
    )

    # convert params with multiple value (e.g., ?id=1,id=2)
    # and/or csv delimited (e.g., id=1,2) into a list.
    @validator('exclude', 'include', pre=True)
    def _param_to_model_filter(cls, value):
        return param_to_list(value)

    @validator('exclude', 'include', pre=True)
    def _exclude_extra_include_value_to_snake(cls, value):
        return values_to_snake(value)

    @property
    def exclude_filter(self):
        """Return excludes in Pydantic filter format.

        https://pydantic-docs.helpmanual.io/usage/exporting_models/#advanced-include-and-exclude
        """
        # return param_to_model_filter(self.exclude)
        filters = ParamModelFilter().generate_params(self.exclude)
        logger.debug(f'event=exclude_filter, filters={filters}')
        return filters

    @property
    def include_filter(self):
        """Return includes in Pydantic filter format.

        https://pydantic-docs.helpmanual.io/usage/exporting_models/#advanced-include-and-exclude
        """
        # return param_to_model_filter(self.include)
        filters = ParamModelFilter().generate_params(self.include)
        logger.debug(f'event=include_filter, filters={filters}')
        return filters

    @property
    def filter_values(self) -> dict[str, Any]:
        """Return filter parameters"""
        return {
            'by_alias': self.by_alias,
            'exclude': self.exclude_filter,
            'exclude_defaults': self.exclude_defaults,
            'exclude_none': self.exclude_none,
            'exclude_unset': self.exclude_unset,
            'include': self.include_filter,
        }

    def to_where(self) -> WhereDict:
        """Convert the object to a where dictionary that can be passed to DAO objects."""
        return None  # type: ignore
