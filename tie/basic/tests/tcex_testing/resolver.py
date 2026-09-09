"""Reference resolution for ${env:X}, ${vault:X}, ${tc:X} patterns.

Shared across all app types. Used by harness input assembly and set_inputs().

Resolution order: env → vault → tc (staged objects)

Usage:
    from tcex_testing.resolver import Resolver

    resolver = Resolver()
    inputs = resolver.resolve({'key': '${env:MY_API_KEY}', 'url': 'https://example.com'})

    # with vault and staged TC objects:
    resolver = Resolver(vault_client=vault, staged=stager.registry)
    inputs = resolver.resolve(inputs)
"""

# standard library
import os
import re
from typing import Any

# third-party
import jmespath

_REF_PATTERN = re.compile(r'\$\{(?P<kind>[^:]+):(?P<name>[^}]+)\}')


class Resolver:
    """Resolves ${kind:name} references in test input values.

    Args:
        env:          Environment dict. Defaults to os.environ at resolve time.
        vault_client: Vault client with a read(path) method. Required for ${vault:} refs.
        staged:       Dict of staged TC objects (from TcStager.registry). Required for ${tc:} refs.
    """

    def __init__(
        self,
        env: dict | None = None,
        vault_client: Any = None,
        staged: dict | None = None,
    ) -> None:
        self._env = env
        self._vault_client = vault_client
        self._staged = staged

    def resolve(self, value: Any) -> Any:
        """Recursively resolve ${kind:name} references in value.

        Handles dicts, lists, and strings. Non-string scalars pass through.

        Full-string match (the entire value is one ref) returns the typed value
        from the source. Embedded match (ref inside a larger string) substitutes
        as a string.
        """
        env = self._env if self._env is not None else dict(os.environ)

        if isinstance(value, dict):
            return {k: self.resolve(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.resolve(item) for item in value]
        if not isinstance(value, str):
            return value

        # Full-string match: return typed value
        full = _REF_PATTERN.fullmatch(value)
        if full:
            return self._resolve_ref(full.group('kind'), full.group('name'), env)

        # Embedded matches: substitute as strings
        def _sub(m: re.Match) -> str:  # type: ignore[type-arg]
            resolved = self._resolve_ref(m.group('kind'), m.group('name'), env)
            return '' if resolved is None else str(resolved)

        return _REF_PATTERN.sub(_sub, value)

    def _resolve_ref(self, kind: str, name: str, env: dict) -> Any:
        if kind == 'env':
            return self._lookup_env(name, env)
        if kind == 'vault':
            if self._vault_client is None:
                raise RuntimeError(f'vault ref ${{vault:{name}}} requires a vault_client')
            return self._vault_client.read(name)
        if kind == 'tc':
            if not self._staged:
                raise RuntimeError(f'tc ref ${{tc:{name}}} requires staged objects')
            return jmespath.search(name, self._staged)
        raise ValueError(f'Unknown ref kind: {kind!r}')

    @staticmethod
    def _lookup_env(name: str, env: dict) -> str | None:
        """Case-insensitive env lookup; normalizes dashes/spaces to underscores."""
        normalized = name.upper().replace('-', '_').replace(' ', '_')
        for key, val in env.items():
            if key.upper().replace('-', '_') == normalized:
                return val
        return None
