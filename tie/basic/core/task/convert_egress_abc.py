"""Egress Convert ABC — base class for converting TC objects to external formats."""

import uuid
from abc import ABC
from collections.abc import Callable

import jmespath

from core.task.task_path_pipe_abc import TaskPathPipeABC


class ConvertEgressABC(TaskPathPipeABC, ABC):
    """Egress convert base class with a transform pipeline and dedup helpers.

    Transforms are callables that receive a single dict and return a modified
    dict, or ``None`` to drop the item. Use :meth:`register_dedup` for
    JMESPath-based deduplication, or :meth:`register_transform` for arbitrary
    pre-convert logic.

    Example::

        class Convert(ConvertEgressABC):
            def __init__(
                self, settings, tcex, db, *, pipeline=None
            ):
                super().__init__(
                    settings, tcex, db, pipeline=pipeline
                )
                self.register_dedup('summary')
    """

    def __init__(self, settings, tcex, db, *, pipeline=None):
        """Initialize the class."""
        super().__init__(settings, tcex, db)
        self.pipeline = pipeline
        self._transforms: list[Callable[[dict], dict | None]] = []
        self._seen: set[str] = set()

    # -- transform pipeline --

    def register_transform(self, fn: Callable[[dict], dict | None]) -> None:
        """Register a transform applied to each object before conversion.

        Args:
            fn: A callable that receives a dict and returns the modified dict,
                or ``None`` to drop the item.
        """
        self._transforms.append(fn)

    def register_dedup(self, expression: str = 'summary') -> None:
        """Register a dedup transform using a JMESPath expression as the key.

        Items whose extracted key has already been seen are dropped (returns
        ``None``). Key matching is case-insensitive for string values.

        Args:
            expression: JMESPath expression evaluated against each object.
                Defaults to ``'summary'`` for flat indicator dedup. Supports
                any valid JMESPath (e.g. ``'tags.data[0].name'``).
        """
        compiled = jmespath.compile(expression)

        def _dedup(obj: dict) -> dict | None:
            value = compiled.search(obj)
            if value is None:
                return obj  # no match = can't dedup, pass through
            normalized = value.lower() if isinstance(value, str) else str(value)
            if normalized in self._seen:
                return None
            self._seen.add(normalized)
            return obj

        self._transforms.append(_dedup)

    def apply_transforms(self, objects: list[dict]) -> list[dict]:
        """Apply all registered transforms to a list of objects.

        Items are dropped when any transform returns ``None``.
        """
        result: list[dict] = []
        for obj in objects:
            for fn in self._transforms:
                obj = fn(obj)
                if obj is None:
                    break
            if obj is not None:
                result.append(obj)
        return result

    # -- dedup helpers --

    @property
    def seen_count(self) -> int:
        """Return the number of unique items seen by dedup transforms."""
        return len(self._seen)

    def reset_seen(self) -> None:
        """Clear the dedup set (e.g. between runs or files)."""
        self._seen.clear()

    # -- deterministic ID generation --

    @staticmethod
    def deterministic_id(namespace: uuid.UUID, value: str) -> str:
        """Generate a deterministic UUID5-based ID for a value.

        Args:
            namespace: UUID namespace for the ID (app-specific constant).
            value: The value to hash (case-insensitive — lowered before hashing).

        Returns:
            A UUID5 string derived from the namespace and lowered value.
        """
        return str(uuid.uuid5(namespace, value.lower()))
