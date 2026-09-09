"""MockSDK — fixture-backed vendor SDK. THIS FILE IS A SKELETON: fill it in.

Subclasses the real SDK so non-HTTP logic (pagination, parsing, model building)
still runs for real. Only the methods that actually reach the vendor API get
overridden, and those read from `self._data` — the fixture dict that
`MockSDKMixin` loads from tests/fixtures/ for the currently running test.

Fixture lookup order (later wins for the same filename stem):
  1. tests/fixtures/common/
  2. tests/fixtures/<TestClassName>/common/
  3. tests/fixtures/<TestClassName>/<test_name>/

So `self._data['events']` resolves to the most specific events.json available
for the running test.

Keep overrides thin. Every bit of logic reimplemented here is logic the tests
stop covering.

Unlike tests/tcex_testing/, this file is yours: template updates will not
overwrite it once you have edited it.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from tcex_testing.fixtures import MockSDKMixin

from sdk.sdk import SDK


class MockSDK(MockSDKMixin, SDK):
    """Fixture-backed mock for this app's SDK.

    MRO note: MockSDKMixin comes first so its fixture plumbing wins over the real
    SDK's implementations for anything it defines.
    """

    def __init__(self, tcex, *args, **kwargs):
        super().__init__(tcex, *args, **kwargs)

    # -- Override only the methods that hit the vendor API ---------------------

    def test_connection(self, settings) -> None:  # noqa: ARG002
        """Connectivity check — always succeeds against fixtures."""
        return None

    def events(self, start_time: Any = None, end_time: Any = None) -> Generator[Any]:  # noqa: ARG002
        """Yield fixture records in place of a live API call.

        Reads tests/fixtures/common/events.json (three sample records), or
        whatever a more specific fixture dir overrides it with — see
        test_download_handles_empty_response for an override in action.

        The `.get(..., [])` default means a missing fixture yields nothing rather
        than raising, so a new test that does not care about events still runs.

        TODO: replace with this app's real SDK methods. Match the real signature
        exactly, including keyword-only args and return type — the whole point is
        that the task under test cannot tell the difference. Replace the fixture
        contents to match your vendor's actual response shape.
        """
        yield from self._data.get('events', [])

    # TODO: add one override per API-calling SDK method, e.g.
    #
    # def enrich(self, type_: str, ids: list[str]) -> list:
    #     return self._data.get(f'enrich_{type_}', [])
