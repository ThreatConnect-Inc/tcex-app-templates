"""Job app profile models."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from tcex_testing.checks import ScopedCheck
from tcex_testing.profile import FetchExpected, Stage


class JobExpected(FetchExpected):
    """Expected assertions for a Job/Organization app run.

    records: TC API fetches to run after the app completes. Each FetchRecord queries
             the TC platform and stores results (a list of TC objects) under record.key.
    checks:  Assertions against fetched records — use Check.on(key) / Check.all() /
             Check.any() / Check.count() / or plain Callables receiving the full
             resolved dict.
    """

    def assert_result(self, result: Any, resolved: dict | None = None) -> None:
        super().assert_result(result, resolved)
        if not (self.records or self.checks):
            return
        for check in self.checks:
            if isinstance(check, ScopedCheck):
                check.assert_against(resolved or {})
            elif callable(check):
                outcome = check(resolved or {})
                if outcome is not None:
                    assert outcome, (
                        f'check {getattr(check, "__name__", check)!r} returned '
                        f'{outcome!r} (expected a truthy value or None)'
                    )


class Profile(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    inputs: dict[str, Any]
    expected: JobExpected = Field(default_factory=JobExpected)
    stage: Stage = Field(default_factory=Stage)
    environments: list[str] = Field(default_factory=list)
    before: Callable[..., None] = Field(default=lambda *_: None)
    after: Callable[..., None] = Field(default=lambda *_: None)

    def fetch_records(self, result: Any) -> dict:
        return self.expected.fetch_records(result)

    def assert_result(self, result: Any, resolved: dict | None = None) -> None:
        self.expected.assert_result(result, resolved)
