"""Assertion primitives — used by all app-type profiles and base classes."""

from __future__ import annotations

# standard library
import base64
import hashlib
import ipaddress
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from collections.abc import Callable

# third-party
import jmespath as _jmespath
from deepdiff import DeepDiff


@dataclass
class CheckOp:
    """A named, callable assertion operation.

    Returned by Check factory methods and passed as expected values in test
    profiles or checker assertions.

        op = Check.contains('hello')
        op('hello world')  # passes
        op('goodbye')      # raises AssertionError
    """

    name: str
    check_fn: Callable[[Any], bool]
    description: str = ''

    def __call__(self, actual: Any) -> None:
        assert self.check_fn(actual), f'Check {self.name!r} failed for value {actual!r}'

    def __repr__(self) -> str:
        return f'CheckOp({self.name!r})'


@dataclass
class ScopedCheck:
    """A check scoped to a specific record key, all records, any record, or the full context.

    Created by Check.on(key) / Check.all() / Check.any() / Check.count().
    Stored in PipelineExpected.checks and executed by the pipeline runner.

    scope='on'      → check applied to records[target]
    scope='all'     → check applied to each record value; all must pass
    scope='any'     → check applied to each record value; at least one must pass
    scope='general' → check_fn receives the full records dict (for count)
    """

    scope: str  # 'on' | 'all' | 'any' | 'general'
    target: str | None  # record key for scope='on', None otherwise
    check: CheckOp

    def assert_against(self, resolved: dict) -> None:
        """Run this check against a resolved records dict."""
        if self.scope == 'on':
            # A missing key is a BROKEN TEST, not an empty result. Defaulting to []
            # made them indistinguishable, so a typo'd key, a glob that matched nothing,
            # or a stage writing to a subdirectory silently satisfied every bounded or
            # negative check — length(0), length_lte(n), not_contains(x), all_match(...)
            # all pass vacuously on an empty list.
            key = self.target or ''
            if key not in resolved:
                msg = (
                    f'ScopedCheck(on={key!r}) has no record to check. '
                    f'Available keys: {sorted(resolved)}. '
                    f'If the stage genuinely produced nothing, assert on a key that '
                    f'exists and resolves to an empty list.'
                )
                raise AssertionError(msg)
            self.check(resolved[key])
        elif self.scope == 'all':
            for data in resolved.values():
                self.check(data)
        elif self.scope == 'any':
            assert any(self._passes(data) for data in resolved.values()), (
                f'ScopedCheck(any) failed: no record passed {self.check.description!r}'
            )
        elif self.scope == 'general':
            self.check(resolved)

    def _passes(self, value: Any) -> bool:
        """Return True if the check passes for value, False otherwise."""
        try:
            self.check(value)
            return True
        except AssertionError:
            return False


class Check:
    """Namespace of reusable assertion factories.

    All methods return a CheckOp or ScopedCheck — nothing is pre-created.

    Type checks (no args):
        Check.is_string(), Check.is_number(), Check.is_bytes(), Check.is_list(),
        Check.is_dict(), Check.is_json(), Check.is_url(), Check.is_date(),
        Check.is_uuid(), Check.is_ip(), Check.is_base64(), Check.is_bool_str(),
        Check.is_not_empty()

    String:
        Check.startswith(prefix), Check.endswith(suffix)
        Check.contains(substring), Check.not_contains(substring)
        Check.regex(pattern)

    Numeric:
        Check.gt(n), Check.lt(n), Check.gte(n), Check.lte(n), Check.between(low, high)

    Collections:
        Check.length(n), Check.length_gt(n), Check.length_gte(n)
        Check.length_lt(n), Check.length_lte(n)
        Check.contains_item(item), Check.in_list(lst), Check.all_match(check_op)

    Binary:
        Check.hash_eq(expected_sha256)

    Structural:
        Check.deep_diff(expected, ignore_order=False), Check.json_eq(expected_dict)
        Check.jmespath(expression, expected)

    Logical:
        Check.not_(check_op), Check.all_of(*check_ops), Check.any_of(*check_ops)

    Scoped (for checks lists in PipelineExpected / UploadExpected / JobExpected):
        Check.on(key), Check.all(), Check.any(), Check.count(min, max)
    """

    # -- Type check factories --------------------------------------------------

    @staticmethod
    def is_string() -> CheckOp:
        def _check(value: Any) -> bool:
            return isinstance(value, str)

        return CheckOp(
            name='is_string', check_fn=_check, description='value is a string'
        )

    @staticmethod
    def is_number() -> CheckOp:
        def _check(value: Any) -> bool:
            if isinstance(value, (int, float)):
                return True
            if isinstance(value, str):
                try:
                    float(value)
                    return True
                except (ValueError, TypeError):
                    return False
            return False

        return CheckOp(
            name='is_number',
            check_fn=_check,
            description='value is numeric (int, float, or numeric string)',
        )

    @staticmethod
    def is_bytes() -> CheckOp:
        def _check(value: Any) -> bool:
            return isinstance(value, (bytes, bytearray))

        return CheckOp(name='is_bytes', check_fn=_check, description='value is bytes')

    @staticmethod
    def is_list() -> CheckOp:
        def _check(value: Any) -> bool:
            return isinstance(value, list)

        return CheckOp(name='is_list', check_fn=_check, description='value is a list')

    @staticmethod
    def is_dict() -> CheckOp:
        def _check(value: Any) -> bool:
            return isinstance(value, dict)

        return CheckOp(name='is_dict', check_fn=_check, description='value is a dict')

    @staticmethod
    def is_json() -> CheckOp:
        def _check(value: Any) -> bool:
            if not isinstance(value, str):
                return False
            try:
                json.loads(value)
                return True
            except (json.JSONDecodeError, TypeError):
                return False

        return CheckOp(
            name='is_json', check_fn=_check, description='value is a valid JSON string'
        )

    @staticmethod
    def is_url() -> CheckOp:
        def _check(value: Any) -> bool:
            return isinstance(value, str) and bool(re.match(r'https?://', value))

        return CheckOp(
            name='is_url', check_fn=_check, description='value is an http/https URL'
        )

    @staticmethod
    def is_date() -> CheckOp:
        def _check(value: Any) -> bool:
            if not isinstance(value, str):
                return False
            formats = (
                '%Y-%m-%d',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%dT%H:%M:%S.%f',
                '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%dT%H:%M:%S.%fZ',
            )
            for fmt in formats:
                try:
                    datetime.strptime(value, fmt)
                    return True
                except ValueError:
                    continue
            try:
                datetime.fromisoformat(value)
                return True
            except (ValueError, AttributeError):
                return False

        return CheckOp(
            name='is_date',
            check_fn=_check,
            description='value is a date/datetime string',
        )

    @staticmethod
    def is_uuid() -> CheckOp:
        def _check(value: Any) -> bool:
            if not isinstance(value, str):
                return False
            try:
                uuid.UUID(value)
                return True
            except ValueError:
                return False

        return CheckOp(
            name='is_uuid', check_fn=_check, description='value is a valid UUID'
        )

    @staticmethod
    def is_ip() -> CheckOp:
        def _check(value: Any) -> bool:
            if not isinstance(value, str):
                return False
            try:
                ipaddress.ip_address(value)
                return True
            except ValueError:
                return False

        return CheckOp(
            name='is_ip',
            check_fn=_check,
            description='value is a valid IP address (v4 or v6)',
        )

    @staticmethod
    def is_base64() -> CheckOp:
        def _check(value: Any) -> bool:
            if not isinstance(value, str):
                return False
            try:
                base64.b64decode(value, validate=True)
                return True
            except Exception:
                return False

        return CheckOp(
            name='is_base64', check_fn=_check, description='value is valid base64'
        )

    @staticmethod
    def is_bool_str() -> CheckOp:
        def _check(value: Any) -> bool:
            return value in {'true', 'false', 'True', 'False'}

        return CheckOp(
            name='is_bool_str',
            check_fn=_check,
            description="value is 'true' or 'false'",
        )

    @staticmethod
    def is_not_empty() -> CheckOp:
        def _check(value: Any) -> bool:
            return bool(value) or value == 0

        return CheckOp(
            name='is_not_empty', check_fn=_check, description='value is not empty/null'
        )

    # -- String checks ---------------------------------------------------------

    @staticmethod
    def startswith(prefix: str) -> CheckOp:
        def _check(value: Any) -> bool:
            return isinstance(value, str) and value.startswith(prefix)

        return CheckOp(
            name='startswith',
            check_fn=_check,
            description=f'value starts with {prefix!r}',
        )

    @staticmethod
    def endswith(suffix: str) -> CheckOp:
        def _check(value: Any) -> bool:
            return isinstance(value, str) and value.endswith(suffix)

        return CheckOp(
            name='endswith', check_fn=_check, description=f'value ends with {suffix!r}'
        )

    @staticmethod
    def contains(substring: str) -> CheckOp:
        def _check(value: Any) -> bool:
            return isinstance(value, (str, list)) and substring in value

        return CheckOp(
            name='contains',
            check_fn=_check,
            description=f'value contains {substring!r}',
        )

    @staticmethod
    def not_contains(substring: str) -> CheckOp:
        def _check(value: Any) -> bool:
            return isinstance(value, (str, list)) and substring not in value

        return CheckOp(
            name='not_contains',
            check_fn=_check,
            description=f'value does not contain {substring!r}',
        )

    @staticmethod
    def regex(pattern: str) -> CheckOp:
        def _check(value: Any) -> bool:
            return bool(re.search(pattern, str(value)))

        return CheckOp(
            name='regex', check_fn=_check, description=f'value matches /{pattern}/'
        )

    # -- Numeric checks --------------------------------------------------------

    @staticmethod
    def gt(n: float) -> CheckOp:
        def _check(value: Any) -> bool:
            try:
                return float(value) > n
            except (TypeError, ValueError):
                return False

        return CheckOp(name='gt', check_fn=_check, description=f'value > {n}')

    @staticmethod
    def lt(n: float) -> CheckOp:
        def _check(value: Any) -> bool:
            try:
                return float(value) < n
            except (TypeError, ValueError):
                return False

        return CheckOp(name='lt', check_fn=_check, description=f'value < {n}')

    @staticmethod
    def gte(n: float) -> CheckOp:
        def _check(value: Any) -> bool:
            try:
                return float(value) >= n
            except (TypeError, ValueError):
                return False

        return CheckOp(name='gte', check_fn=_check, description=f'value >= {n}')

    @staticmethod
    def lte(n: float) -> CheckOp:
        def _check(value: Any) -> bool:
            try:
                return float(value) <= n
            except (TypeError, ValueError):
                return False

        return CheckOp(name='lte', check_fn=_check, description=f'value <= {n}')

    @staticmethod
    def between(low: float, high: float) -> CheckOp:
        def _check(value: Any) -> bool:
            try:
                return low <= float(value) <= high
            except (TypeError, ValueError):
                return False

        return CheckOp(
            name='between', check_fn=_check, description=f'{low} <= value <= {high}'
        )

    # -- Collection checks -----------------------------------------------------

    @staticmethod
    def length(n: int) -> CheckOp:
        def _check(value: Any) -> bool:
            return hasattr(value, '__len__') and len(value) == n

        return CheckOp(name='length', check_fn=_check, description=f'length == {n}')

    @staticmethod
    def length_gt(n: int) -> CheckOp:
        def _check(value: Any) -> bool:
            return hasattr(value, '__len__') and len(value) > n

        return CheckOp(name='length_gt', check_fn=_check, description=f'length > {n}')

    @staticmethod
    def length_gte(n: int) -> CheckOp:
        def _check(value: Any) -> bool:
            return hasattr(value, '__len__') and len(value) >= n

        return CheckOp(name='length_gte', check_fn=_check, description=f'length >= {n}')

    @staticmethod
    def length_lt(n: int) -> CheckOp:
        def _check(value: Any) -> bool:
            return hasattr(value, '__len__') and len(value) < n

        return CheckOp(name='length_lt', check_fn=_check, description=f'length < {n}')

    @staticmethod
    def length_lte(n: int) -> CheckOp:
        def _check(value: Any) -> bool:
            return hasattr(value, '__len__') and len(value) <= n

        return CheckOp(name='length_lte', check_fn=_check, description=f'length <= {n}')

    @staticmethod
    def contains_item(item: Any) -> CheckOp:
        def _check(value: Any) -> bool:
            return hasattr(value, '__contains__') and item in value

        return CheckOp(
            name='contains_item',
            check_fn=_check,
            description=f'collection contains {item!r}',
        )

    @staticmethod
    def in_list(lst: list) -> CheckOp:
        def _check(value: Any) -> bool:
            return value in lst

        return CheckOp(name='in_list', check_fn=_check, description=f'value in {lst!r}')

    @staticmethod
    def all_match(check_op: CheckOp) -> CheckOp:
        def _check(value: Any) -> bool:
            return isinstance(value, list) and all(check_op.check_fn(i) for i in value)

        return CheckOp(
            name='all_match',
            check_fn=_check,
            description=f'all items pass {check_op.description}',
        )

    # -- Binary ----------------------------------------------------------------

    @staticmethod
    def hash_eq(expected_sha256: str) -> CheckOp:
        """Assert SHA256 of the actual value matches the expected hex digest."""

        def _check(actual: Any) -> bool:
            if actual is None:
                return False
            if isinstance(actual, str):
                actual = actual.encode('utf-8')
            return hashlib.sha256(actual).hexdigest() == expected_sha256

        return CheckOp(
            name='hash_eq',
            check_fn=_check,
            description=f'SHA256 == {expected_sha256[:16]}...',
        )

    # -- Structural ------------------------------------------------------------

    @staticmethod
    def jmespath(expression: str, expected: Any) -> CheckOp:
        """Extract via jmespath then assert the result matches expected."""

        def _check(value: Any) -> bool:
            extracted = _jmespath.search(expression, value)
            if isinstance(expected, CheckOp):
                return expected.check_fn(extracted)
            if callable(expected):
                return bool(expected(extracted))
            if expected is None:
                return extracted is None
            return extracted == expected

        return CheckOp(
            name='jmespath',
            check_fn=_check,
            description=f'jmespath {expression!r} matches {expected!r}',
        )

    @staticmethod
    def deep_diff(expected: Any, ignore_order: bool = False) -> CheckOp:
        def _check(actual: Any) -> bool:
            return len(DeepDiff(actual, expected, ignore_order=ignore_order)) == 0

        return CheckOp(
            name='deep_diff',
            check_fn=_check,
            description=f'deep diff against {expected!r}',
        )

    @staticmethod
    def json_eq(expected: dict) -> CheckOp:
        """Assert actual JSON string parses equal to expected."""

        def _check(actual: Any) -> bool:
            if isinstance(actual, str):
                try:
                    actual = json.loads(actual)
                except (json.JSONDecodeError, TypeError):
                    return False
            return len(DeepDiff(actual, expected, ignore_order=False)) == 0

        return CheckOp(
            name='json_eq',
            check_fn=_check,
            description=f'JSON parses equal to {repr(expected)[:40]}...',
        )

    # -- Logical ---------------------------------------------------------------

    @staticmethod
    def not_(check_op: CheckOp) -> CheckOp:
        def _check(value: Any) -> bool:
            return not check_op.check_fn(value)

        return CheckOp(
            name='not_', check_fn=_check, description=f'NOT ({check_op.description})'
        )

    @staticmethod
    def all_of(*check_ops: CheckOp) -> CheckOp:
        def _check(value: Any) -> bool:
            return all(c.check_fn(value) for c in check_ops)

        return CheckOp(
            name='all_of',
            check_fn=_check,
            description='all of: ' + ', '.join(c.description for c in check_ops),
        )

    @staticmethod
    def any_of(*check_ops: CheckOp) -> CheckOp:
        def _check(value: Any) -> bool:
            return any(c.check_fn(value) for c in check_ops)

        return CheckOp(
            name='any_of',
            check_fn=_check,
            description='any of: ' + ', '.join(c.description for c in check_ops),
        )

    # -- Scoped check builders -------------------------------------------------

    @staticmethod
    def on(key: str) -> CheckScopeBuilder:
        """Scope checks to a specific record key.

        Check.on('sightings').is_not_empty()
        Check.on('reports').deep_diff([...])
        """
        return CheckScopeBuilder(scope='on', target=key)

    @staticmethod
    def all() -> CheckScopeBuilder:
        """Scope checks across all records — all must pass.

        Check.all().is_not_empty()
        Check.all().length_gt(0)
        """
        return CheckScopeBuilder(scope='all')

    @staticmethod
    def any() -> CheckScopeBuilder:
        """Scope checks across all records — at least one must pass.

        Check.any().contains('malware')
        """
        return CheckScopeBuilder(scope='any')

    @staticmethod
    def count(min: int | None = None, max: int | None = None) -> ScopedCheck:
        """Assert total item count across all resolved records."""

        def _check(records: dict) -> bool:
            total = sum(
                len(v) if hasattr(v, '__len__') else 1 for v in records.values()
            )
            if min is not None and total < min:
                return False
            if max is not None and total > max:
                return False
            return True

        return ScopedCheck(
            scope='general',
            target=None,
            check=CheckOp(
                name='count',
                check_fn=_check,
                description=f'total item count: min={min}, max={max}',
            ),
        )


# Type alias for values accepted in checks lists across all expected models.
CheckLike = ScopedCheck | Callable[..., Any]


class CheckScopeBuilder:
    """Builder returned by Check.on() / Check.all() / Check.any().

    Proxies every Check factory method, wrapping the result in a ScopedCheck.

        Check.on('sightings').is_not_empty()
        Check.on('sightings').deep_diff([...])
        Check.all().length_gt(0)
        Check.any().contains('malware')
    """

    def __init__(self, scope: str, target: str | None = None) -> None:
        self._scope = scope
        self._target = target

    def __getattr__(self, name: str) -> Any:
        attr = getattr(Check, name)
        if callable(attr):

            def _wrapper(*args: Any, **kwargs: Any) -> ScopedCheck:
                return ScopedCheck(
                    scope=self._scope,
                    target=self._target,
                    check=attr(*args, **kwargs),  # type: ignore[arg-type]
                )

            return _wrapper
        raise AttributeError(name)
