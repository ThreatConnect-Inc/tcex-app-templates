"""Database Paginator Module"""

import logging
import urllib.parse
from collections.abc import Iterable
from datetime import date
from functools import cached_property
from typing import TYPE_CHECKING, Generic, TypeVar

from pydantic.main import BaseModel

# get primary API logger
logger = logging.getLogger('APP_REGISTRY')

T = TypeVar('T', bound=BaseModel)


if TYPE_CHECKING:
    from model import FilterParamPaginatedModel


class Paginator(Generic[T]):
    """Database Paginator Class"""

    def __init__(
        self,
        data: Iterable[T],
        url_domain: str,
        url_path: str,
        params: 'FilterParamPaginatedModel',
    ):
        """Initialize class properties."""
        self.data = data
        self.url = f'https://{url_domain}{url_path}'
        self.params = params

        self._loaded_data = []

    def query_params(self, offset: int) -> str:
        """Return previous query params"""
        _query_params = [
            f'limit={self.params.limit}',
            f'offset={offset}',
        ]
        for name, value in self.params.model_dump(exclude_none=True, exclude_unset=True).items():
            # limit and offset will be replaced
            if name in ('limit', 'offset'):
                continue

            # rename include (pydantic name) to fields (alias - our name)
            name = 'field' if name == 'include' else name

            if isinstance(value, list):
                for v in value:
                    v = urllib.parse.quote_plus(v)
                    _query_params.append(f'{name}={v}')
            elif isinstance(value, bool):
                value = str(value).lower()
                _query_params.append(f'{name}={value}')
            elif isinstance(value, date):
                value = urllib.parse.quote_plus(value.strftime('%Y-%m-%d'))
                _query_params.append(f'{name}={value}')
            elif hasattr(value, '__name__'):
                # handle sort_order
                value = urllib.parse.quote_plus(value.__name__)
                _query_params.append(f'{name}={value}')
            else:
                logger.debug(f'{name}={value}')
                value = urllib.parse.quote_plus(value)
                _query_params.append(f'{name}={value}')

        return '&'.join(_query_params)

    @cached_property
    def page_data(self) -> list[T]:
        """Return page data."""
        iterator = iter(self.data)
        try:
            consumed = 0
            while consumed < self.params.offset:
                consumed += 1
                next(iterator)

            consumed = 0
            while consumed < self.params.limit:
                consumed += 1
                self._loaded_data.append(next(iterator))
        except StopIteration:
            pass

        return self._loaded_data

    @property
    def next_url(self) -> str | None:
        """Return the next URL for pagination."""
        # If we got a full page, there are likely more results
        if len(self.page_data) >= self.params.limit:
            offset = self.params.offset + self.params.limit
            return f'{self.url}?{self.query_params(offset)}'
        return None

    @property
    def previous_url(self) -> str | None:
        """Return the previous URL for pagination."""
        offset = self.params.offset - self.params.limit
        if offset >= 0:
            return f'{self.url}?{self.query_params(offset)}'
        return None

    @cached_property
    def total_count(self) -> int:
        """Return total count of records returned for query."""
        return len(self._loaded_data)
