"""Job DAO."""

# standard library

# third-party

# standard library
import contextlib
from collections.abc import Iterable
from pathlib import Path

# third-party
from core.api.validation.models.query_param_filter_pagination_model import (
    QueryParamFilterPaginationModel,
)
from core.json_db import JsonDB
from core.json_db import where as where_m
from core.json_db.dao import JsonDBDAO
from core.json_db.json_db import SortBy
from core.model.tie.batch_error_model import (
    BatchErrorModel,
    JobBatchErrorIndexModel,
    UnknownBatchErrorModel,
    error_codes_model_map,
    error_codes_name_map,
)


class BatchErrorDAO(JsonDBDAO[BatchErrorModel]):
    """Job Request DAO"""

    def __init__(self, db: JsonDB):
        """."""
        super().__init__(db, BatchErrorModel)

    def get_all_for_request(
        self, request_id: str, *, model_type: type[BatchErrorModel] | None = None
    ):
        """Get all errors for a request."""
        batch_errors = self.get_error_ids_for_request(request_id)

        for error_id in batch_errors:
            error = self.db.load(BatchErrorModel, error_id)
            if model_type is not None:
                if isinstance(error, model_type):
                    yield error
            else:
                yield error

    def get_error_ids_for_request(self, request_id: str) -> list[str]:
        """Get paths for all errors for the index for the given request."""
        batch_errors = []
        for path in self.db.get_paths(JobBatchErrorIndexModel):
            if request_id.casefold() in path.stem.casefold():
                entity = self.db.load_from_path(JobBatchErrorIndexModel, path)
                if entity is not None:
                    batch_errors.extend(entity.error_ids)

        batch_errors.sort()
        return batch_errors

    def get_page_for_query_params(
        self,
        query_params: QueryParamFilterPaginationModel,
        *,
        request_id: str | None = None,
        error_code: str | None = None,
    ):
        """Get a page of data for the given filters."""
        sort_by = query_params.sort

        if isinstance(sort_by, str):
            with contextlib.suppress(KeyError):
                sort_by = SortBy[sort_by.upper()]

        model = BatchErrorModel
        if error_code:
            model = error_codes_model_map.get(error_code, UnknownBatchErrorModel)

        # pylint: disable=isinstance-second-argument-not-valid-type
        error_paths = self.db.get_paths(
            model,
            sort_by=sort_by if isinstance(sort_by, SortBy) else SortBy.INDEX,
            sort_order=query_params.sort_order,
        )
        if request_id:
            error_paths = self._filter_errors_by_request(request_id, error_paths)

        where = query_params.to_where() or {}
        if isinstance(where, dict) and len([v for v in where.values() if v is not None]) == 0:
            where = None
        else:
            where = where_m.where(where)

        if where:  # Trying to avoid checking where(error) for every iteration if possible
            errors = []
            for path in error_paths:
                error = self.db.load_from_path(model, path)
                if error is not None and where(error):
                    errors.append(error)
        else:
            errors = self.db.load_paths(model, error_paths)

        if not isinstance(
            sort_by,
            SortBy,  # pylint: disable=isinstance-second-argument-not-valid-type
        ):
            errors.sort(
                key=lambda x: getattr(x, sort_by),
                reverse=query_params.sort_order == 'desc',
            )

        page_data = (
            errors[query_params.offset : query_params.offset + query_params.limit]
            if query_params.limit
            else errors[query_params.offset :]
        )

        return {
            'totalCount': len(errors),
            'count': len(page_data),
            'data': page_data,
        }

    def get_all_for_query_params(
        self,
        query_params: QueryParamFilterPaginationModel,
        *,
        request_id: str | None = None,
        error_code: str | None = None,
    ):
        """Get a page of data for the given filters."""
        model = BatchErrorModel
        if error_code:
            model = error_codes_model_map.get(error_code, UnknownBatchErrorModel)

        # pylint: disable=isinstance-second-argument-not-valid-type
        error_paths = self.db.get_paths(model)
        if request_id:
            error_paths = self._filter_errors_by_request(request_id, error_paths)

        where = query_params.to_where() or {}
        if isinstance(where, dict) and len([v for v in where.values() if v is not None]) == 0:
            where = None
        else:
            where = where_m.where(where)

        if where:  # Trying to avoid checking where(error) for every iteration if possible
            errors = []
            for path in error_paths:
                error = self.db.load_from_path(model, path)
                if error is not None and where(error):
                    errors.append(error)
        else:
            errors = self.db.load_paths(model, error_paths)

        return errors

    def get_error_counts_by_code(self, request_id: str | None = None):
        """Get error counts by code."""
        if request_id is None:
            data = []
            for code, type_ in error_codes_model_map.items():
                count = len(self.db.get_paths(type_))
                if count:
                    data.append(
                        {
                            'count': count,
                            'error': error_codes_name_map[code],
                            'code': code,
                        }
                    )
        else:
            data = []

            request_error_ids = self.get_error_ids_for_request(request_id)

            for code, type_ in error_codes_model_map.items():
                error_path = self.db.get_paths(type_)
                count = len([p for p in error_path if p.name.split('.')[0] in request_error_ids])

                if count:
                    data.append(
                        {
                            'count': count,
                            'error': error_codes_name_map[code],
                            'code': code,
                        }
                    )

        data = [d for d in data if d['count'] > 0]
        data.append({'count': sum(d['count'] for d in data), 'error': 'All', 'code': 'All'})

        data.sort(key=lambda x: x['error'], reverse=False)

        return data

    def _filter_errors_by_request(self, request_id: str, error_paths: list[Path]) -> Iterable[Path]:
        """Filter errors by request ID."""
        error_ids = set(self.get_error_ids_for_request(request_id))
        for error_path in error_paths:
            if error_path.name.split('.')[0] in error_ids:
                yield error_path
