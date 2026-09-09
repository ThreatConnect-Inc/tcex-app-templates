"""AppResult — returned by AppRunner.run()."""
from __future__ import annotations

from typing import Any

from tcex_testing.checker import _dispatch


class AppResult:
    """Result from a playbook app run.

    Provides direct assertions on exit code, exit message, and output variables.
    """

    def __init__(self, exit_code: int, exit_message: str | None, outputs: dict) -> None:
        self.exit_code = exit_code
        self.exit_message = exit_message
        self._outputs = outputs

    def output(self, name: str) -> Any:
        """Return deserialized output value by clean variable name."""
        return self._outputs.get(name)

    def assert_exit_code(self, expected: int) -> None:
        assert self.exit_code == expected, (
            f'exit_code: expected {expected!r}, got {self.exit_code!r}'
        )

    def assert_output(self, name: str, expected: Any) -> None:
        """Assert output equals expected value, or passes a Check callable."""
        actual = self._outputs.get(name)
        _dispatch(actual, expected, f'output {name!r}')
