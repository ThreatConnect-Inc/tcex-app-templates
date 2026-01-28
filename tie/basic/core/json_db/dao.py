"""Data Access Object for JsonDB."""

# standard library
from collections.abc import Callable
from contextlib import suppress
from typing import Any, Generic, TypeAlias, TypedDict, TypeVar, cast

# third-party
from pydantic import BaseModel

# first-party
from core.api.validation.models.query_param_filter_pagination_model import (
    QueryParamFilterPaginationModel,
)
from core.json_db import JsonDB, SortBy, SortOrder
from core.json_db import where as where_m

M = TypeVar('M', bound=BaseModel)

TotalCount: TypeAlias = int
WhereCallable: TypeAlias = Callable[[M], bool]


class PageData(TypedDict):
    """Type for a page of data to return from the API."""

    totalCount: int
    count: int
    data: list


class JsonDBDAO(Generic[M]):
    """Data Access Object for JsonDB."""

    def __init__(self, db: JsonDB, model: type[M]) -> None:
        """."""
        self.db = db
        self.model = model
        self.index_field = self.db.get_index_field(model)

    def delete(self, model: M) -> None:
        """Delete a model from the database."""
        self.db.delete(model)

    def get(self, model_id: str) -> M:
        """Get a model from the database."""
        return self.db.load(self.model, model_id)

    def save(self, model: M) -> None:
        """Save a model to the database."""
        self.db.save(model)

    def get_page_for_query_params(
        self,
        query_params: QueryParamFilterPaginationModel,
    ) -> dict[str, int | list[Any] | str]:
        """Get a page of data based on query parameters."""
        data, total_count = self.get_all_with_total_count(
            where=query_params.to_where(),
            sort_by=query_params.sort,
            sort_order=query_params.sort_order,
            offset=query_params.offset,
            limit=query_params.limit,
        )

        return {
            'totalCount': total_count,
            'count': len(data),
            'data': data,
        }

    def get_all(
        self,
        *,
        where: dict[str, Callable[[Any], bool] | None] | WhereCallable | None = None,
        sort_by: SortBy | str = SortBy.INDEX,
        sort_order: SortOrder | str = SortOrder.ASC,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[M]:
        """Get data matching where with limit and offset and sort."""
        return self.get_all_with_total_count(
            where=where,
            sort_by=sort_by,
            sort_order=sort_order,
            offset=offset,
            limit=limit,
        )[0]

    def get_all_with_total_count(  # noqa: C901
        self,
        /,
        where: dict[str, Callable[[Any], bool] | None] | WhereCallable | None = None,
        sort_by: SortBy | str = SortBy.INDEX,
        sort_order: SortOrder | str = SortOrder.ASC,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[M], TotalCount]:
        """Get data matching where with limit and offset and sort, with total count."""
        if isinstance(where, dict) and len([v for v in where.values() if v is not None]) == 0:
            where = None

        if isinstance(sort_by, str):
            with suppress(KeyError):
                sort_by = SortBy[sort_by.upper()]

        # optimization: if we're sorting by a SortBy value, with no filters, we don't have to
        # load everything
        # pylint: disable=isinstance-second-argument-not-valid-type
        if where is None and isinstance(sort_by, SortBy):
            paths = self.db.get_paths(self.model, sort_by=sort_by, sort_order=sort_order)
            sliced_paths = paths[offset : limit + offset if limit else limit]
            data = self.db.load_paths(self.model, sliced_paths)
            total_count = len(paths)

            return data, total_count

        # optimization: if we're filtering by the index field, we can use the index to filter
        # without having to load data before filtering.
        if (
            where is not None
            and not callable(where)
            and len(where) == 1
            and self.index_field in where
        ):
            filter_fn = cast('Callable', where[self.index_field])

            # pylint: disable=isinstance-second-argument-not-valid-type
            if isinstance(sort_by, SortBy):
                paths = self.db.get_paths(self.model, sort_by=sort_by, sort_order=sort_order)

                # pylint: disable=protected-access
                paths = [p for p in paths if filter_fn(self.db.get_index_from_path(p))]
                sliced_paths = paths[offset : limit + offset if limit else limit]
                data = self.db.load_paths(self.model, sliced_paths)
                total_count = len(paths)
                return data, total_count

            paths = self.db.get_paths(self.model)
            # pylint: disable=protected-access
            paths = [p for p in paths if filter_fn(self.db.get_index_from_path(p))]
            sliced_paths = paths[offset : limit + offset if limit else limit]
            data = self.db.load_paths(self.model, sliced_paths)
            data.sort(key=lambda x: getattr(x, sort_by), reverse=sort_order == SortOrder.DESC)

            total_count = len(paths)

            return data, total_count

        match where:
            case dict():
                where_val = where_m.where(where)
            case Callable():
                where_val = where
            case None:
                where_val = None

        if isinstance(sort_by, SortBy):  # pylint: disable=isinstance-second-argument-not-valid-type
            results = list(
                self.db.load_all(
                    self.model,
                    where=where_val,
                    sort_by=sort_by,
                    sort_order=sort_order,
                )
            )
        elif isinstance(sort_by, str):
            results = list(self.db.load_all(self.model, where=where_val))
            results.sort(
                key=lambda x: getattr(x, sort_by),
                reverse=sort_order == SortOrder.DESC,
            )
        else:
            results = list(self.db.load_all(self.model, where=where_val))

        return results[offset : offset + limit] if limit else results[offset:], len(results)
