"""Egress Download ABC — helpers for downloading from ThreatConnect via TQL."""

import logging
from abc import ABC
from collections.abc import Generator
from datetime import datetime, timedelta

from tcex.api.tc.v3.object_collection_abc import ObjectCollectionABC

from core.task.download_abc import DownloadABC

logger = logging.getLogger('tcex')


class TqlBuilder:
    """Fluent TQL query builder.

    Usage::

        tql = (
            TqlBuilder()
            .owners(['TCI', 'Common Community'])
            .indicator_types(['Address', 'Host'])
            .date_range('lastModified', start, end)
            .raw('confidence > 50')
            .build()
        )
    """

    def __init__(self):
        """Initialize an empty builder."""
        self._clauses: list[str] = []

    # -- object types --

    def owners(self, names: list[str]) -> 'TqlBuilder':
        """Filter by owner names."""
        if names:
            quoted = ','.join(f'"{n}"' for n in names)
            self._clauses.append(f'ownerName in ({quoted})')
        return self

    def indicator_types(self, types: list[str]) -> 'TqlBuilder':
        """Filter by indicator type names (e.g. Address, Host, File:MD5)."""
        if types:
            # Strip sub-type qualifiers (File:MD5 -> File) and dedupe
            base_types = {t.split(':')[0] for t in types}
            quoted = ','.join(f'"{t}"' for t in sorted(base_types))
            self._clauses.append(f'typeName in ({quoted})')
        return self

    def group_types(self, types: list[str]) -> 'TqlBuilder':
        """Filter by group type names (e.g. Adversary, Campaign)."""
        if types:
            quoted = ','.join(f'"{t}"' for t in types)
            self._clauses.append(f'typeName in ({quoted})')
        return self

    # -- date ranges --

    def date_range(
        self, field: str, start: str | datetime | None, end: str | datetime | None
    ) -> 'TqlBuilder':
        """Add a date range clause for the given field.

        Args:
            field: TQL field name (e.g. 'lastModified', 'dateAdded').
            start: Inclusive start (ISO string or datetime). Omit for open-ended.
            end: Exclusive end (ISO string or datetime). Omit for open-ended.
        """
        if start is not None:
            self._clauses.append(f'{field} >= "{_to_iso(start)}"')
        if end is not None:
            self._clauses.append(f'{field} < "{_to_iso(end)}"')
        return self

    # -- raw / escape hatch --

    def raw(self, tql: str) -> 'TqlBuilder':
        """Append a raw TQL clause."""
        if tql:
            self._clauses.append(f'({tql})')
        return self

    # -- output --

    def build(self) -> str:
        """Return the assembled TQL string."""
        return ' AND '.join(self._clauses)

    def __str__(self) -> str:
        """Return the assembled TQL string."""
        return self.build()

    def __bool__(self) -> bool:
        """Return True if any clauses have been added."""
        return bool(self._clauses)


class DynamicPageSizer:
    """Tracks response timing and adjusts resultLimit dynamically.

    After each API response, call :meth:`adjust` with the elapsed time.
    Read :attr:`limit` before the next request.
    """

    def __init__(
        self,
        start: int = 1_000,
        minimum: int = 1_000,
        maximum: int = 10_000,
        slow_threshold: timedelta = timedelta(minutes=2),
        fast_threshold: timedelta = timedelta(seconds=30),
    ):
        """Initialize with page size bounds and timing thresholds."""
        self.limit = start
        self.minimum = minimum
        self.maximum = maximum
        self.slow_threshold = slow_threshold
        self.fast_threshold = fast_threshold

    def adjust(self, elapsed: timedelta) -> int:
        """Adjust page size based on response elapsed time. Returns new limit."""
        if elapsed > self.slow_threshold and self.limit > self.minimum:
            self.limit = max(int(self.limit // 2), self.minimum)
        elif elapsed < self.fast_threshold and self.limit < self.maximum:
            self.limit = min(int(self.limit * 1.5), self.maximum)
        return self.limit


_VALID_DIRECTIONS = {'ASC', 'DESC'}


def _to_iso(value: str | datetime) -> str:
    """Normalize a datetime or string to ISO format."""
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%dT%H:%M:%SZ')
    return value


def _validate_sorting(sorting: list[tuple[str, str]]) -> str:
    """Validate and normalize sorting tuples to a TC API sorting string.

    Accepts direction in any case (e.g. 'asc', 'DESC'), normalizes to uppercase.

    Returns:
        API sorting string, e.g. ``"lastModified ASC id DESC"``.

    Raises:
        ValueError: If any direction is not ASC or DESC.
    """
    parts = []
    for field, direction in sorting:
        direction = direction.upper()
        if direction not in _VALID_DIRECTIONS:
            msg = f'Invalid sort direction "{direction}" for field "{field}". Must be ASC or DESC.'
            raise ValueError(msg)
        parts.append(f'{field} {direction}')
    return ' '.join(parts)


class DownloadEgressABC(DownloadABC, ABC):
    """Egress download base class with TQL and pagination helpers.

    Provides :meth:`iterate` for paginating over TC v3 API objects with optional
    dynamic page sizing and ID-based pagination. Concrete tasks call this from
    their ``download()`` implementation.
    """

    def iterate(
        self,
        tc_object: ObjectCollectionABC,
        tql: str | TqlBuilder,
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
            tql: TQL query string or :class:`TqlBuilder` instance.
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
        if sorting and paginate_via_id:
            msg = (
                'Cannot combine sorting with paginate_via_id. '
                'ID-based pagination requires sorting=ID ASC.'
            )
            raise ValueError(msg)

        sorting_str = _validate_sorting(sorting) if sorting else None
        tql_str = str(tql)

        if paginate_via_id:
            yield from self._iterate_by_id(
                tc_object,
                tql_str,
                result_limit=result_limit,
                dynamic_page_size=dynamic_page_size,
                fields=fields,
            )
        else:
            yield from self._iterate_by_tcex(
                tc_object,
                tql_str,
                result_limit=result_limit,
                fields=fields,
                sorting=sorting_str,
            )

    def _iterate_by_tcex(
        self,
        tc_object: ObjectCollectionABC,
        tql: str,
        *,
        result_limit: int = 10_000,
        fields: list[str] | None = None,
        sorting: str | None = None,
    ) -> Generator:
        """Iterate using tcex's built-in pagination (follows ``next`` URLs)."""
        params = {'resultLimit': result_limit}
        if fields:
            params['fields'] = fields
        if sorting:
            params['sorting'] = sorting

        tc_object.params = params
        tc_object.tql.set_raw_tql(tql)

        yield from tc_object

    def _iterate_by_id(
        self,
        tc_object: ObjectCollectionABC,
        tql: str,
        *,
        result_limit: int = 10_000,
        dynamic_page_size: bool = False,
        fields: list[str] | None = None,
    ) -> Generator:
        """Iterate using ``sorting=ID ASC`` + ``ID > highest_id``.

        Bypasses tcex's built-in pagination for deterministic ordering and
        resume support. Uses the tcex session for authenticated requests.
        """
        sizer = DynamicPageSizer(start=result_limit) if dynamic_page_size else None
        session = tc_object._session  # noqa: SLF001
        api_endpoint = tc_object._api_endpoint  # noqa: SLF001

        highest_id = None
        total_yielded = 0

        while True:
            # Build per-page TQL
            page_tql = tql
            if highest_id is not None:
                page_tql = f'({tql}) AND id > {highest_id}' if tql else f'id > {highest_id}'

            page_limit = sizer.limit if sizer else result_limit
            params: dict = {
                'tql': page_tql,
                'resultLimit': page_limit,
                'sorting': 'id ASC',
                'createActivityLog': 'false',
            }
            if fields:
                params['fields'] = fields

            response = session.request(
                'GET',
                api_endpoint,
                params=params,
                headers={'content-type': 'application/json'},
            )

            if not response.ok:
                msg = response.text or response.reason
                raise RuntimeError(f'API request failed: {response.status_code} — {msg}')

            body = response.json()
            data = body.get('data', [])

            if sizer:
                sizer.adjust(response.elapsed)
                self.log.debug(
                    f'action=dynamic-page-size, elapsed={response.elapsed}, '
                    f'limit={sizer.limit}, results={len(data)}'
                )

            if not data:
                break

            yield from data

            total_yielded += len(data)
            highest_id = data[-1].get('id')

            # Fewer results than requested means we've exhausted the dataset
            if len(data) < page_limit:
                break

        self.log.debug(f'action=iterate-by-id-complete, total={total_yielded}')

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
