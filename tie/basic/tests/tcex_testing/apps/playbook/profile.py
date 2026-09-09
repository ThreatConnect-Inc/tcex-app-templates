"""Playbook app profile models."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from tcex_testing.checker import _dispatch
from tcex_testing.profile import Expected, Stage


class PlaybookExpected(Expected):
    """Expected assertions for a playbook app run."""

    outputs: dict[str, Any] | None = None

    def assert_result(self, result: Any, resolved: dict | None = None) -> None:
        super().assert_result(result, resolved)
        if self.outputs is not None:
            for name, expected in self.outputs.items():
                _dispatch(result.output(name), expected, f'output {name!r}')


class Profile(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    inputs: dict[str, Any]
    expected: PlaybookExpected = Field(default_factory=PlaybookExpected)
    stage: Stage = Field(default_factory=Stage)
    environments: list[str] = Field(default_factory=list)
    before: Callable[..., None] = Field(default=lambda *_: None)
    after: Callable[..., None] = Field(default=lambda *_: None)

    def fetch_records(self, result: Any) -> dict:
        return self.expected.fetch_records(result)

    def assert_result(self, result: Any, resolved: dict | None = None) -> None:
        self.expected.assert_result(result, resolved)
