"""Resource Base Class"""
# standard library
import logging
import traceback
from abc import ABC
from typing import TYPE_CHECKING, Any, List, Optional, Union

# third-party
import falcon
from more import Paginator
from pydantic import BaseModel
from sqlalchemy import ARRAY, Integer, cast, func
from sqlalchemy.dialects import sqlite
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Query

if TYPE_CHECKING:
    # third-party
    from model import SettingsModel
    from sqlalchemy.orm import scoped_session
    from tasks import Tasks
    from tcex import TcEx

logger = logging.getLogger('tcex')


class ResourceABC(ABC):
    """Resource Base Class"""

    # define middleware properties for linting
    error = callable
    log: 'logging.Logger' = logger
    response_media = callable  # more->validation->response_media
    session: 'scoped_session'
    settings: 'SettingsModel'
    tasks: 'Tasks'
    tcex: 'TcEx'

    def _db_add_record(self, record: Any, error_description: str):
        """Add DB record."""
        try:
            self.session.add(record)
            self.session.commit()
        except IntegrityError as ex:
            err = self.error(
                description=error_description,
                exception=traceback.format_exc().split('\n'),
                title='Conflict',
            )
            raise falcon.HTTPConflict(**err) from ex
        except Exception as ex:
            err = self.error(
                description=error_description,
                exception=traceback.format_exc().split('\n'),
                title='Internal Server Error',
            )
            raise falcon.HTTPInternalServerError(**err) from ex

    def _db_create_record(self, schema: Any, data: dict, error_description: str):
        """Create DB record."""
        try:
            return schema(**data)
        except Exception as ex:
            err = self.error(
                description=error_description,
                exception=traceback.format_exc().split('\n'),
                title='Internal Server Error',
            )
            raise falcon.HTTPInternalServerError(**err) from ex

    def _db_delete_record(self, record: Any, error_description: str):
        """Delete DB record."""
        try:
            self.session.delete(record)
            self.session.commit()
        except Exception as ex:
            err = self.error(
                description=error_description,
                exception=traceback.format_exc().split('\n'),
                title='Internal Server Error',
            )
            raise falcon.HTTPInternalServerError(**err) from ex

    def _db_delete_all(self, query: Query, error_description: str):
        """Delete DB record."""
        try:
            query.delete()
        except Exception as ex:
            err = self.error(
                description=error_description,
                exception=traceback.format_exc().split('\n'),
                title='Internal Server Error',
            )
            raise falcon.HTTPInternalServerError(**err) from ex

    def _db_get_record(
        self, query: Query, method: str, error_description: str
    ) -> Union[Any, List[Any]]:
        """Return DB record(s)."""
        try:
            return getattr(query, method)()
        except NoResultFound as ex:
            err = self.error(
                description='Item not found.',
                exception=traceback.format_exc().split('\n'),
                title='Not Found',
            )
            raise falcon.HTTPNotFound(**err) from ex
        except Exception as ex:
            err = self.error(
                description=error_description,
                exception=traceback.format_exc().split('\n'),
                title='Internal Server Error',
            )
            raise falcon.HTTPInternalServerError(**err) from ex

    def _db_log_query(self, query: Query):
        """Log the provided query."""
        try:
            query_string = query.statement.compile(
                compile_kwargs={'literal_binds': True}, dialect=sqlite.dialect()
            )
        except Exception:
            query_string = query.statement.compile(
                compile_kwargs={'literal_binds': False}, dialect=sqlite.dialect()
            )
        self.log.debug(f'event=log-query, query={query_string}')

    def _db_log_result(self, results: Any):
        """Log one or more ORM result."""
        if not isinstance(results, list):
            results = [results]

        for result in results:
            result = {c.name: str(getattr(result, c.name)) for c in result.__table__.columns}
            self.log.debug(f'event=log-result, result={result}')

    @staticmethod
    def _db_paginator(
        query: Query,
        req: falcon.request,
        sort: callable,
    ) -> Paginator:
        """Return DB paginator."""
        return Paginator(
            query=query,
            # url_domain=self.settings.app_registry_domain,
            url_domain='fix-me',
            url_path=req.path,
            params=req.context.params,
            sort=sort,
            sort_order=req.context.params.sort_order,
        )

    def _db_patch_record(self, record: Any, error_description: str):
        """Patch DB Record."""
        try:
            self.session.add(record)
            self.session.commit()
        except Exception as ex:
            err = self.error(
                description=error_description,
                exception=traceback.format_exc().split('\n'),
                title='Internal Server Error',
            )
            raise falcon.HTTPInternalServerError(**err) from ex

    def _db_sort(
        self,
        params: BaseModel,
        schema: Any,
        schema_alt: Optional[Any] = None,
        default_sort: Optional[str] = 'name',
    ) -> callable:
        """Return DB sort."""
        # customize sort for this endpoint
        sort = params.sort.lower() if params.sort is not None else default_sort

        if hasattr(schema, sort):
            sort_field = getattr(schema, sort)
        elif schema_alt and hasattr(schema_alt, sort):
            sort_field = getattr(schema_alt, sort)
        else:
            err = self.error(
                description=(
                    f'Invalid sort field "{sort}" provided. For valid field names '
                    'send a request to this endpoint with HTTP OPTION method.'
                ),
                title='Bad Request',
            )
            raise falcon.HTTPBadRequest(**err)

        if sort == 'version':
            return cast(func.string_to_array(sort_field, '.'), ARRAY(Integer))
        return sort_field
