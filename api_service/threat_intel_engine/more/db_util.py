"""DB Util Module"""
# standard library
import logging
from typing import TYPE_CHECKING, Any

# third-party
from sqlalchemy.dialects import sqlite
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Query

# get tcex logger
logger = logging.getLogger('tcex')

if TYPE_CHECKING:
    # third-party
    from sqlalchemy.orm import Session


# pylint: disable=no-member
class DbUtil:
    """DB Util Module"""

    def __init__(self):
        """Initialize class properties"""

        # properties
        self.log = logger

    def add_record(
        self, session: 'Session', record: Any, error_description: str, raise_exception: bool = False
    ):
        """Add DB record."""
        try:
            session.add(record)
            session.commit()
        except IntegrityError as ex:
            self.log.exception(error_description)
            if raise_exception is True:
                raise ex
        except Exception as ex:
            self.log.exception(error_description)
            if raise_exception is True:
                raise ex

    def create_record(
        self, schema: Any, data: dict, error_description: str, raise_exception: bool = False
    ):
        """Create DB record."""
        try:
            return schema(**data)
        except Exception as ex:
            self.log.exception(error_description)
            if raise_exception is True:
                raise ex
        return None

    def delete_record(
        self, session: 'Session', record: Any, error_description: str, raise_exception: bool = False
    ):
        """Delete DB record."""
        try:
            session.delete(record)
            session.commit()
        except Exception as ex:
            self.log.exception(error_description)
            if raise_exception is True:
                raise ex

    def delete_all(self, query: Query, error_description: str, raise_exception: bool = False):
        """Delete DB record."""
        try:
            query.delete()
        except Exception as ex:
            self.log.exception(error_description)
            if raise_exception is True:
                raise ex

    def get_record(
        self, query: Query, method: str, error_description: str, raise_exception: bool = False
    ) -> Any | list[Any]:
        """Return DB record(s)."""
        try:
            return getattr(query, method)()
        except NoResultFound as ex:
            self.log.exception(error_description)
            if raise_exception is True:
                raise ex
        except Exception as ex:
            self.log.exception(error_description)
            if raise_exception is True:
                raise ex
        return None

    def log_query(self, query: Query):
        """Log the provided query."""
        try:
            query_string = query.statement.compile(
                compile_kwargs={'literal_binds': True}, dialect=sqlite.dialect()
            )
        except Exception:
            query_string = query.statement.compile(
                compile_kwargs={'literal_binds': False}, dialect=sqlite.dialect()
            )
        self.log.trace(f'event=log-query, query={query_string}')

    def log_result(self, results: Any):
        """Log one or more ORM result."""
        if not isinstance(results, list):
            results = [results]

        for result in results:
            result = {c.name: str(getattr(result, c.name)) for c in result.__table__.columns}
            self.log.debug(f'event=log-result, result={result}')

    def patch_record(
        self, session: 'Session', record: Any, error_description: str, raise_exception: bool = False
    ):
        """Patch DB Record."""
        try:
            session.add(record)
            session.commit()
        except Exception as ex:
            self.log.exception(error_description)
            if raise_exception is True:
                raise ex
