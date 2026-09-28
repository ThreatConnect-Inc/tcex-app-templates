"""Task Module — Egress "Preview" (STIX dry run, no upload, nothing persisted)."""

import itertools
from abc import ABC, abstractmethod
from functools import cached_property

import arrow
from pydantic import BaseModel

from core.model.tcve.tql_config_model import TqlConfigPostModel, build_owner_type_tql
from core.service.tcve.tql_iterator_service import TqlIteratorService

PREVIEW_RESULT_CAP = 100


class PreviewResult(BaseModel):
    """Result of a Preview dry run."""

    total_count: int
    returned_count: int
    cap: int
    truncated: bool
    stix_objects: list[dict]


class PreviewTQLConfigABC(ABC):
    """Runs a bounded, read-only dry run of the download+convert pipeline for a TQL config.

    Never uploads anything and never persists anything (no `JobRecord`, no `db.save()`,
    no files written to disk) — constructed from just `tcex`/`settings`, unlike `Download`/
    `Convert` (whose `TaskABC.__init__` opens a Redis namespace and writes several keys on
    construction, making them unsafe to instantiate per request).
    """

    def __init__(self, tcex, settings, fields: list[str] | None = None):
        """Initialize class properties."""
        self.tcex = tcex
        self.settings = settings
        self.log = tcex.log
        self.fields = fields or []

    @cached_property
    def _iterator_service(self) -> TqlIteratorService:
        """The shared pagination service (`TqlIteratorService`) this preview delegates to."""
        return TqlIteratorService(self.tcex, self.log)

    def run(self, tql_config: TqlConfigPostModel, cap: int = PREVIEW_RESULT_CAP) -> PreviewResult:
        """Run one bounded TC v3 query and convert up to *cap* matches to STIX.

        `resultLimit` only sets the page *size* each request returns — pagination keeps
        following pages until the *entire* result set is exhausted, regardless of
        `resultLimit`. For a broad TQL matching tens of thousands of indicators, iterating
        without an explicit stop would make hundreds of sequential HTTP requests and never
        return in practice — `itertools.islice(indicators, cap)` below is what actually
        bounds this to (usually) a single page/request, not `resultLimit`. `islice` (not a
        plain `for` + manual counter + `break`) matters here: a `for` loop's protocol pulls
        the *next* item before the loop body's `break` check runs, so a manual counter
        would fetch one item beyond the cap — for `resultLimit == cap`-sized pages, that
        one extra item is the first item of page 2, silently triggering an unnecessary
        second HTTP request. `islice` caps the number of `next()` calls directly, so
        exactly `cap` items are ever pulled from the underlying generator.

        Unlike the real download, this applies no `lastModified` job-window filter — it
        shows the full historical match set for the TQL/owners/types as configured, not
        an incremental slice.
        """
        tql, owner_params = build_owner_type_tql(tql_config)
        if 'owner' in owner_params:
            # TqlIteratorService.iterate() takes a TQL string only, with no way to pass the
            # REST-level `owner` param build_owner_type_tql() prefers for a single owner —
            # fold the same scoping into the TQL clause instead.
            tql = f'({tql}) and ownerName == "{owner_params["owner"]}"'

        tc_object = self.tcex.api.tc.v3.indicators()

        indicators = self._iterator_service.iterate(
            tc_object,
            tql,
            paginate_via_id=True,
            dynamic_page_size=True,
            result_limit=cap if cap < 10_000 else 10_000,
            fields=self.fields,
        )

        transformed_objects: list[dict] = []
        for i in itertools.islice(indicators, cap):
            i = self.transform_indicator(i)
            if not isinstance(i, list):
                i = [i]
            transformed_objects.extend(i)

        transformed_objects = self.finalize_transformed_objects(transformed_objects)

        transformed_objects = transformed_objects[:cap]

        response = self._iterator_service.call_tc(
            tc_object._session,  # noqa: SLF001
            tc_object._api_endpoint,  # noqa: SLF001
            {'count': 'true', 'resultLimit': 1, 'tql': tql},
        )
        total_count = response.json().get('count', -1)

        return PreviewResult(
            total_count=total_count,
            returned_count=len(transformed_objects),
            cap=cap,
            truncated=total_count > len(transformed_objects),
            stix_objects=transformed_objects,
        )

    @abstractmethod
    def transform_indicator(self, indicator: dict) -> dict | list[dict]:
        """Hook for subclasses to modify indicators before conversion."""
        raise NotImplementedError('Subclasses must implement transform_indicator()')

    def finalize_transformed_objects(self, transformed_objects: list[dict]) -> list[dict]:
        """Hook for subclasses to modify the list of transformed objects before returning."""
        return transformed_objects

    def _add_valid_until(self, stix_ioc: dict) -> dict:
        """Replace the integer TTL placeholder in *valid_until* with an ISO timestamp.

        A STIX-emitting Convert task may store TTL as an integer (hours from now) rather
        than a resolved timestamp; a preview subclass paired with such a Convert task
        should resolve *valid_until* the same way here so the preview shows what will
        actually be uploaded rather than the raw placeholder. Formatted with millisecond
        precision and a literal ``Z`` so it matches ``valid_from`` and the rest of the
        STIX object, instead of `.isoformat()`'s microseconds + ``+00:00``.

        If TTL is 0, *valid_until* is removed entirely (missing ``valid_until`` is
        treated as non-expiring).
        """
        ttl_hours = stix_ioc.get('valid_until')
        if ttl_hours is None:
            return stix_ioc
        if ttl_hours != 0:
            stix_ioc['valid_until'] = (
                arrow.utcnow().shift(hours=ttl_hours).format('YYYY-MM-DDTHH:mm:ss.SSS') + 'Z'
            )
        else:
            del stix_ioc['valid_until']
        return stix_ioc
