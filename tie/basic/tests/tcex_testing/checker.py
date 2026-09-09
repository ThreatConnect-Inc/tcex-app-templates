"""_dispatch — shared assertion helper used by PlaybookChecker and JobChecker.

CheckerABC was removed — it was only used by DownloadChecker/ConvertChecker
which are also gone (replaced by the Profile/PipelineExpected flow).
"""

# standard library
from typing import Any

from tcex_testing.checks import CheckOp


def _dispatch(actual: Any, expected: Any, label: str) -> None:
    """Shared assertion dispatch — same logic used by all checker methods."""
    if isinstance(expected, CheckOp):
        expected(actual)
    elif expected is None:
        assert actual is None, f'{label}: expected None, got {actual!r}'
    elif callable(expected):
        result = expected(actual)
        if result is not None:
            assert result, f'{label}: callable check returned falsy for {actual!r}'
    else:
        assert actual == expected, f'{label}: expected {expected!r}, got {actual!r}'
