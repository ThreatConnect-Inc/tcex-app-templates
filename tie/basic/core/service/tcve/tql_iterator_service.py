"""TQL Iterator Service — TC v3 TQL pagination helpers, usable outside a task lifecycle.

Extracted from `DownloadEgressABC` so the same pagination logic can be shared by both
task-scoped download classes (which compose this service) and request-scoped callers
(e.g. a preview endpoint) that cannot subclass `DownloadEgressABC`/`TaskABC` — that base
class's `__init__` opens a Redis namespace and writes keys on construction, which is
unsafe to do per HTTP request. `TqlIteratorService` is constructed from just `tcex`/`log`,
with no such dependency.
"""

import logging
from collections.abc import Generator
from datetime import timedelta

from requests import Response
from tcex.api.tc.v3.object_collection_abc import ObjectCollectionABC

logger = logging.getLogger('tcex')


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


class TqlIteratorService:
    """TQL pagination helper, constructed from just `tcex`/`log`.

    Provides :meth:`iterate` for paginating over TC v3 API objects with optional
    dynamic page sizing and ID-based pagination. Composed by `DownloadEgressABC`
    for task-scoped callers, and usable directly by request-scoped callers that
    cannot subclass `DownloadEgressABC`/`TaskABC`.
    """

    def __init__(self, tcex, log=None):
        """Initialize class properties."""
        self.tcex = tcex
        self.log = log or tcex.log

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

            response = self.call_tc(session, api_endpoint, params)

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

    def call_tc(self, session, api_endpoint: str, params: dict) -> Response:
        """Make one GET request against `api_endpoint` and verify the response."""
        response = session.request(
            'GET',
            api_endpoint,
            params=params,
            headers={'content-type': 'application/json'},
        )
        return self.verify_response(response)

    def verify_response(self, response: Response) -> Response:
        """Raise if `response` indicates a failed request, otherwise return it unchanged."""
        if not response.ok:
            msg = response.text or response.reason
            raise RuntimeError(f'API request failed: {response.status_code} — {msg}')
        return response
