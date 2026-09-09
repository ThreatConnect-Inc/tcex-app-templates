"""DB Util Module"""

# REVIEW (template cleanup, 2026-08-25): retained pending a decision -- confirm with the
# team whether this is a supported extension point for app authors or leftover.
# It was proposed for deletion, then kept because "no importers" does not prove much
# in a template: files here exist to be used by apps built FROM it.
# Evidence at the time:
#   Imports sqlalchemy, which is NOT in requirements.txt -- importing this module would raise
#   ImportError. Predates the move to JsonDB. Apps that want it keep an app-local copy instead
#   (see tcvf-mandiant-advantage-intel/more/db_util.py).

import logging
from sqlite3 import OperationalError
from typing import Any

from sqlalchemy.dialects import sqlite
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Query, Session

# get tcex logger
logger = logging.getLogger('tcex')


class DbUtil:
    """DB Util Module"""

    def __init__(self):
        """Initialize class properties"""
        # properties
        self.log = logger

    def add_record(
        self,
        session: Session,
        record: Any,
        error_description: str,
        raise_exception: bool = False,
    ):
        """Add DB record."""
        try:
            session.add(record)
            session.commit()
        except IntegrityError:
            self.log.exception(error_description)
            if raise_exception is True:
                raise
        except Exception:
            self.log.exception(error_description)
            if raise_exception is True:
                raise

    def create_record(
        self,
        schema: Any,
        data: dict,
        error_description: str,
        raise_exception: bool = False,
    ):
        """Create DB record."""
        try:
            return schema(**data)
        except Exception:
            self.log.exception(error_description)
            if raise_exception is True:
                raise
        return None

    def delete_record(
        self,
        session: Session,
        record: Any,
        error_description: str,
        raise_exception: bool = False,
    ):
        """Delete DB record."""
        try:
            session.delete(record)
            session.commit()
        except Exception:
            self.log.exception(error_description)
            if raise_exception is True:
                raise

    def delete_all(self, query: Query, error_description: str, raise_exception: bool = False):
        """Delete DB record."""
        try:
            query.delete()
        except Exception:
            self.log.exception(error_description)
            if raise_exception is True:
                raise

    def get_record(
        self,
        query: Query,
        method: str,
        error_description: str,
        raise_exception: bool = False,
    ) -> Any | list[Any]:
        """Return DB record(s)."""
        try:
            return getattr(query, method)()
        except NoResultFound:
            self.log.exception(error_description)
            if raise_exception is True:
                raise
        except OperationalError:
            self.log.exception(f'Exception should be raised: {raise_exception}')
            if raise_exception is True:
                raise
        except Exception:
            self.log.exception(error_description)
            if raise_exception is True:
                raise
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
        self,
        session: Session,
        record: Any,
        error_description: str,
        raise_exception: bool = False,
    ):
        """Patch DB Record."""
        try:
            session.add(record)
            session.commit()
        except Exception:
            self.log.exception(error_description)
            if raise_exception is True:
                raise
