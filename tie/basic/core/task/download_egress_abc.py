"""Egress Download ABC — helpers for downloading from ThreatConnect via TQL."""

import logging
from abc import ABC
from collections.abc import Generator
from functools import cached_property

from tcex.api.tc.v3.object_collection_abc import ObjectCollectionABC

from core.service.tcve.tql_iterator_service import (
    DynamicPageSizer,  # noqa: F401 - re-exported for backwards compatibility
    TqlIteratorService,
)
from core.task.download_abc import DownloadABC

logger = logging.getLogger('tcex')

__all__ = ['DownloadEgressABC', 'DynamicPageSizer']


class DownloadEgressABC(DownloadABC, ABC):
    """Egress download base class with TQL and pagination helpers.

    Provides :meth:`iterate` for paginating over TC v3 API objects with optional
    dynamic page sizing and ID-based pagination. Concrete tasks call this from
    their ``download()`` implementation.

    The pagination implementation itself lives in :class:`TqlIteratorService`
    (`core/service/tcve/tql_iterator_service.py`), shared with request-scoped
    callers that cannot subclass this task-lifecycle-bound class.
    """

    @cached_property
    def _iterator_service(self) -> TqlIteratorService:
        """The shared pagination service this task delegates to."""
        return TqlIteratorService(self.tcex, self.log)

    def iterate(
        self,
        tc_object: ObjectCollectionABC,
        tql: str,
        *,
        paginate_via_id: bool = False,
        dynamic_page_size: bool = False,
        result_limit: int = 10_000,
        fields: list[str] | None = None,
        sorting: list[tuple[str, str]] | None = None,
    ) -> Generator:
        """Iterate over a TC v3 collection with configurable pagination.

        Args:
            tc_object: A tcex collection object (e.g. ``tcex.api.tc.v3.indicators()``).
            tql: TQL query string.
            paginate_via_id: Use ``sorting=ID ASC`` + ``ID > highest_id`` instead
                of tcex's built-in ``next`` URL pagination. Required for
                deterministic ordering and resume support.
            dynamic_page_size: Automatically adjust ``resultLimit`` based on
                response timing.
            result_limit: Starting (or fixed) page size.
            fields: Optional list of fields to request from the API.
            sorting: Custom sorting as a list of ``(field, direction)`` tuples,
                e.g. ``[('lastModified', 'ASC'), ('id', 'DESC')]``. Direction
                is case-insensitive and normalized to uppercase. Cannot be
                combined with ``paginate_via_id`` since ID-based pagination
                requires ``sorting=ID ASC``.

        Yields:
            Individual TC objects (indicators, groups, etc.).

        Raises:
            ValueError: If ``sorting`` and ``paginate_via_id`` are both set,
                or if a sort direction is invalid.
        """
        yield from self._iterator_service.iterate(
            tc_object,
            tql,
            paginate_via_id=paginate_via_id,
            dynamic_page_size=dynamic_page_size,
            result_limit=result_limit,
            fields=fields,
            sorting=sorting,
        )

    @staticmethod
    def lazy_chunk(iterable, size: int) -> Generator[list, None, None]:
        """Yield successive fixed-size lists without materializing the full sequence."""
        chunk: list = []
        for item in iterable:
            chunk.append(item)
            if len(chunk) >= size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk
