"""Shared profile building blocks — used by all app-type profile modules."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from tcex_testing.checks import CheckLike


class StagedItem(BaseModel):
    """A TC v3 object to create before a test run and delete after.

    key:    Registry key — access the created object at stager.registry[key].
    path:   TC v3 API path (e.g. 'indicators/addresses', 'groups/reports').
    body:   Request body passed to the TC API to create the object.
    params: Query parameters (e.g. {'fields': ['attribute', 'tag']}) to control
            the response shape returned after creation.
    """

    key: str
    path: str
    body: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)


class Stage(BaseModel):
    threatconnect: list[StagedItem] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class Expected(BaseModel):
    """Base assertions common to every app type.

    NOTE the `extra = 'forbid'` below. `outputs=` belongs to `PlaybookExpected`, not
    here, and pydantic v1's default `Extra.ignore` used to drop it silently — so
    `Expected(exit_codes=[0], outputs={...})` constructed fine, asserted nothing, and
    passed on exit code alone. Forbidding extras turns that into a loud error at
    construction instead of a green test that checked nothing.
    """

    class Config:
        extra = 'forbid'

    exit_codes: list[int] = Field(default_factory=lambda: [0])
    exit_message: str | None = None

    def fetch_records(self, result: Any) -> dict:
        """Fetch any external records needed for assertion. Override in subclasses."""
        return {}

    def assert_exit_code(self, result: Any) -> None:
        assert result.exit_code in self.exit_codes, (
            f'Exit code {result.exit_code!r} not in {self.exit_codes}\n'
            f'Exit message: {result.exit_message!r}'
        )

    def assert_exit_message(self, result: Any) -> None:
        if self.exit_message is not None:
            assert result.exit_message == self.exit_message, (
                f'Exit message mismatch\n'
                f'  expected: {self.exit_message!r}\n'
                f'  actual:   {result.exit_message!r}'
            )

    def assert_result(self, result: Any, resolved: dict | None = None) -> None:
        """Assert result against expected values. Subclasses call super() then add their own."""
        self.assert_exit_code(result)
        self.assert_exit_message(result)


class FetchRecord(BaseModel):
    """Describes a TC API fetch to retrieve records for assertion after an upload.

    key:    Label — referenced in checks via Check.on(key).
    path:   TC v3 API path (e.g. 'indicators/addresses', 'groups/reports').
    params: Query parameters passed to the TC API. Typically:
            'tql'    — TQL filter string
                       e.g. 'dateAdded > "1 hour ago" AND ownerName = "TCI"'
            'fields' — list of attribute names to include in the response

    The fetch returns a list of matching TC objects stored under record.key.
    Used by both TIE (UploadExpected) and Job (JobExpected).
    """

    key: str
    path: str
    params: dict[str, Any] = Field(default_factory=dict)


class FetchExpected(Expected):
    """Base for expected models that fetch TC objects after a run.

    Shared by JobExpected and TIE's UploadExpected.
    """

    records: list[FetchRecord] = Field(default_factory=list)
    checks: list[CheckLike] = Field(default_factory=list)

    def fetch_records(self, result: Any) -> dict:
        """Fetch TC objects via the v3 API for each FetchRecord."""
        resolved: dict[str, Any] = {}
        for record in self.records:
            response = result.tcex.session.tc.get(
                f'/v3/{record.path}',
                params=record.params,
            )
            response.raise_for_status()
            resolved[record.key] = response.json().get('data', [])
        return resolved
