"""Database Paginator Module"""
# standard library
import logging
import urllib.parse
from datetime import date
from typing import TYPE_CHECKING

# third-party
from sqlalchemy import func
from sqlalchemy.exc import ProgrammingError
from tcex.backports import cached_property

if TYPE_CHECKING:
    # third-party
    from model import PaginatorResponseModel
    from sqlalchemy.orm.query import Query

# get primary API logger
logger = logging.getLogger('APP_REGISTRY')


class Paginator:
    """Database Paginator Class"""

    def __init__(
        self,
        query: 'Query',
        url_domain: str,
        url_path: str,
        params: 'PaginatorResponseModel',
        sort: callable,
        sort_order: any,
    ):
        """Initialize class properties."""
        self._query = query
        self.url = f'https://{url_domain}{url_path}'
        self.params = params
        self.sort = sort
        self.sort_order = sort_order

    @property
    def query(self):
        """Return the update query."""
        return (
            self._query.order_by(self.sort_order(self.sort))
            .offset(self.params.offset)
            .limit(self.params.limit)
        )

    def query_params(self, offset: int) -> str:
        """Return previous query params"""
        _query_params = [
            f'limit={self.params.limit}',
            f'offset={offset}',
        ]
        for name, value in self.params.dict(exclude_none=True, exclude_unset=True).items():
            # limit and offset will be replaced
            if name in ('limit', 'offset'):
                continue

            # rename include (pydantic name) to fields (alias - our name)
            name = 'field' if name == 'include' else name

            if isinstance(value, list):
                for v in value:
                    v = urllib.parse.quote_plus(v)
                    _query_params.append(f'{name}={v}')
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

    @property
    def next_url(self) -> str:
        """Return the next URL for pagination."""
        offset = self.params.offset + self.params.limit
        if offset < self.total_count:  # pylint: disable=comparison-with-callable
            return f'{self.url}?{self.query_params(offset)}'
        return None

    @property
    def previous_url(self) -> str:
        """Return the previous URL for pagination."""
        offset = self.params.offset - self.params.limit
        if offset >= 0:
            return f'{self.url}?{self.query_params(offset)}'
        return None

    @cached_property
    def total_count(self) -> int:
        """Return total count of records returned for query."""
        try:
            # https://gerrit.sqlalchemy.org/c/sqlalchemy/sqlalchemy/+/2973
            # total_query = self._query.statement.with_only_columns([func.count()]).order_by(None)
            total_query = (
                self._query.statement.select_from(*self._query.statement.columns_clause_froms)
                .with_only_columns([func.count()])
                .order_by(None)
            )
            return self._query.session.execute(total_query).scalar()
        except ProgrammingError:
            return 0
