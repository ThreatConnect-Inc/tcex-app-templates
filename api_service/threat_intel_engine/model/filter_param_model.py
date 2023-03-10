"""Base Request Filter Model"""
# standard library
import logging
from enum import Enum
from typing import Optional, Type

# third-party
from pydantic import BaseModel, Extra, Field, conint, validator
from sqlalchemy import asc, desc

# get primary API logger
logger = logging.getLogger('tcex')


def param_to_list(values) -> list:
    """Convert multiple or single params to a list."""
    logger.debug(f'values={values}, type-value={type(values)}')
    if isinstance(values, list):
        return [v for raw_value in values for v in raw_value.split(',')]

    if isinstance(values, str):
        return values.split(',')

    return values


def param_to_model_filter(values) -> dict:
    """Convert multiple or single params to Pydantic include/exclude filter.

    https://pydantic-docs.helpmanual.io/usage/exporting_models/#advanced-include-and-exclude

    Example:
    * 'one,two,three.a' -> {'one': True, 'two': True, 'three': {'a'}}
    * ['one,two', 'three'] -> {'one': True, 'two': True, 'three': True}
    * ['one', 'two', 'three.a.b.c'])) -> {'one': True, 'two': True, 'three': {'a': {'b': {'c'}}}}
    * ['one', 'two', 'three.a|b|c'])) -> {'one': True, 'two': True, 'three': {'a', 'c', 'b'}}
    * ['one', 'two', 'three.a.b.c', 'three.a.b.d', 'three.a.f'])) ->
        {'one': True, 'two': True, 'three': {'a': {'b': {'c', 'd'}, 'f': True}}}
    """
    nested_key_delimiter = '|'  # delimiter for multiple nested keys
    param_delimiter = ','  # delimiter for multiple params in a single query param
    path_delimiter = '.'  # delimiter for path keys

    def _nested(parts, params):
        """Process nested path and key values."""
        if len(parts) > 2:
            params.setdefault(parts[0], {})

            # remove the first item and recursively call _nested
            _nested(parts[1:], params[parts[0]])
        else:
            params.setdefault(parts[0], set())
            if isinstance(params[parts[0]], dict):
                # set value (one.a) to {'one': 'a': True}
                params[parts[0]][parts[1]] = True
            elif nested_key_delimiter in parts[1]:
                # set value (one.a|b|c) to dict with set {'one': {'a', 'b', 'c'}}
                params[parts[0]].update(parts[1].split(nested_key_delimiter))
            else:
                # set value (one.a, one.b, one.c) to dict with set {'one': {'a', 'b', 'c'}}
                params[parts[0]].add(parts[1])

    # normalize inputs
    if isinstance(values, list):
        normalized_values = [
            v.strip() for raw_value in values for v in raw_value.split(param_delimiter)
        ]
    elif isinstance(values, str):
        normalized_values = values.split(param_delimiter)
    else:
        return values

    # process inputs to return dict of bool, sets
    params = {}
    for param in normalized_values:
        if path_delimiter in param:
            # handle nested values w/multi-key support (e.g. 'one.a.b.c' and 'one.a|b|c')
            _nested(param.split(path_delimiter), params)
        else:
            # handle single value (e.g., 'one')
            params[param] = True
    return params


class FilterParamModel(BaseModel, extra=Extra.forbid):
    """Model and validation for on_get() method."""

    exclude: Optional[list] = Field(
        None, description='One or more fields to exclude from response.'
    )
    exclude_defaults: bool = Field(False, description='Exclude any field that has a default value.')
    exclude_none: bool = Field(
        True,
        alias='exclude_null',
        description='Exclude any field that has a null value.',
    )
    exclude_unset: bool = Field(True, description='Exclude any field that was not explicitly set.')
    include: Optional[list] = Field(
        None,
        alias='field',
        description='One or more fields to include in response (alias for include).',
    )

    # convert params with multiple value (e.g., ?id=1,id=2)
    # and/or csv delimited (e.g., id=1,2) into a list.
    _param_to_model_filter = validator('exclude', 'include', allow_reuse=True, pre=True)(
        param_to_list
    )

    @property
    def exclude_filter(self):
        """Return excludes in Pydantic filter format.

        https://pydantic-docs.helpmanual.io/usage/exporting_models/#advanced-include-and-exclude
        """
        return param_to_model_filter(self.exclude)

    @property
    def include_filter(self):
        """Return includes in Pydantic filter format.

        https://pydantic-docs.helpmanual.io/usage/exporting_models/#advanced-include-and-exclude
        """
        return param_to_model_filter(self.include)


# define pagination inputs
LimitInt: Type[int] = conint(ge=0, le=500)
OffsetInt: Type[int] = conint(ge=0)


class SortOrder(str, Enum):
    """Enum for possible sort orders."""

    asc = 'asc'
    desc = 'desc'


# pylint: disable=no-self-argument
class FilterParamPaginatedModel(FilterParamModel):
    """Model and validation for on_get() method."""

    limit: Optional[LimitInt] = 50
    offset: Optional[OffsetInt] = 0
    sort: Optional[str] = Field(None, description='The field name used to sort the results.')
    sort_order: Optional[SortOrder] = Field(SortOrder.asc, description='The sort order: asc|desc.')

    @validator('sort_order', always=True)
    def _sort_order(cls, v):
        """Validate sort order."""
        if v.lower() == 'asc':
            v = asc
        elif v.lower() == 'desc':
            v = desc
        else:
            raise ValueError(f'Invalid sort order: {v}')
        return v
