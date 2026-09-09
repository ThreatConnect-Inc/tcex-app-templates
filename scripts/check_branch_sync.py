#!/usr/bin/env python3
"""Check v2/v3 branch sync — flag non-pydantic divergence.

Diffs two branches and classifies each changed line as pydantic-migration
or unexpected divergence.  Exits 0 if only pydantic diffs remain, 1 if
real divergence is found.

Usage:
    python scripts/check_branch_sync.py              # defaults: v2..v3
    python scripts/check_branch_sync.py v2 v3        # explicit branches
    python scripts/check_branch_sync.py --verbose    # show matched patterns
"""

from __future__ import annotations

import re
import subprocess  # nosec B404
import sys

# ---------------------------------------------------------------------------
# Pydantic v1 <-> v2 patterns.  A changed line matching ANY of these is
# considered an expected pydantic-migration diff.
# ---------------------------------------------------------------------------
PYDANTIC_PATTERNS: list[re.Pattern] = [
    re.compile(p)
    for p in [
        # -- imports --
        r'from pydantic import',
        r'from pydantic\s',
        r'from pydantic\.fields',
        r'from pydantic\.generics',
        r'from pydantic\.typing',
        r'from pydantic_core',
        r'from typing import',
        r'from types import',
        r'import pydantic',
        r'import json',  # removed in some v2 migrations
        # -- decorators --
        r'@validator\b',
        r'@field_validator\b',
        r'@root_validator',
        r'@model_validator',
        r'@field_serializer',
        r'@classmethod',  # added alongside model/field_validator in v2
        # -- config class / model_config --
        r'class Config[:(]',
        r'model_config\s*=',
        r'ConfigDict\(',
        r'Extra\.',
        r"extra\s*=\s*['\"]",
        r'extra\s*=\s*Extra\.',
        r'allow_population_by_field_name',
        r'populate_by_name',
        r'validate_all\b',
        r'validate_default\b',
        r'orm_mode',
        r'from_attributes',
        r'json_encoders',
        r'arbitrary_types_allowed',
        r'validate_assignment',
        r'alias_generator',
        # -- config values that change format (dict-style vs class-style) --
        # v1: alias_generator = foo  vs  v2: alias_generator=foo,
        # These are the same setting, just formatted differently.
        r'^\s*\w+\s*=\s*\w+,?\s*$',  # bare key=value lines inside Config/ConfigDict
        # -- serialization / methods --
        r'\.dict\(',
        r'\.model_dump\(',
        r'\.model_dump_json\(',
        r'\.json\(',
        r'\.parse_obj\(',
        r'\.model_validate\(',
        r'\.parse_raw\(',
        r'\.model_validate_json\(',
        r'parse_obj_as',
        r'TypeAdapter',
        r'\.schema\(\)',
        r'\.model_json_schema\(\)',
        # -- field defaults (v2 requires explicit = None for Optional fields) --
        r':\s*([\w.]+\s*\|?\s*)*None\s*$',  # v1: field: Type | None
        r':\s*([\w.]+\s*\|?\s*)*None\s*=\s*None',  # v2: field: Type | None = None
        # -- field internals --
        r'__fields__',
        r'__dict__',
        r'model_fields\b',
        r'field_info\.extra',
        r'json_schema_extra',
        r'Undefined\b',
        r'PydanticUndefined',
        r'model_info\.',
        r'\.type_\b',
        r'\.outer_type_',
        r'get_origin\(',
        r'get_args\(',
        r'get_inner_type',
        r'_get_json_schema_extra',
        # -- generics --
        r'GenericModel\b',
        r'GenericAlias',
        # -- validator signature changes --
        # v1: def fn(cls, v)  vs  v2: def fn(cls, v: str) -> str
        # v1: def fn(cls, _, values)  vs  v2: def fn(cls, values: dict) -> dict
        r'def _\w+\(cls,',
        r'def _\w+\(self',
        r'allow_reuse',
        r'pre=True',
        r'always=True',
        r'mode=',
        # -- validator body changes (cross-field access patterns) --
        r'values\.get\(',
        r'self\.\w+',  # v2 model_validator(mode='after') uses self.field
        r'isinstance\(values,\s*dict\)',
        # -- error handling changes --
        r'\.errors\(\)',
        r"\.pop\('url'",
        # -- json_db internals --
        r'issubclass\(',
        r'NoArgAnyCallable',
        r'AbstractSetIntStr',
        r'MappingIntStrAny',
        r'TYPE_CHECKING',
        r'if callable\(',
        r'return extra',
        # -- class definition changes (v2 drops extra= from class line) --
        r'^class \w+\((?:ItemModel|BaseModel|ModelBase)',
        # -- serializer body (json_encoders lambda → field_serializer method) --
        r'lambda v:',
        r'\.strftime\(',
        r'\.isoformat\(\)',
        r'\.replace\(tzinfo=',
        r'def serialize_',
        # -- misc pydantic --
        r'model_rebuild',
        r'update_forward_refs',
        r'\.copy\(',
        r'\.model_copy\(',
        r'model_construct',
        r'\.construct\(',
        # -- removed arrow imports (unused after pydantic v2 migration) --
        r'from arrow import',
        # -- optional field defaults (v2 requires = None explicitly) --
        r':\s*[\w.\[\]]+\s*\|\s*None\s*$',  # v1: field: list[dict] | None
        r':\s*[\w.\[\]]+\s*\|\s*None\s*=',  # v2: field: list[dict] | None = None
        r'minWidth.*noqa',  # field with noqa that also gets = None
        # -- method kwarg lines (by_alias, exclude_none, etc.) --
        r'by_alias\s*=',
        r'exclude_none\s*=',
        r'exclude_unset\s*=',
        r'exclude=',
        # -- pydantic v2 schema ref path change --
        r'#/definitions/',  # v1 schema ref
        r'#/\$defs/',  # v2 schema ref
        # -- pydantic v2 removed sort_keys from json --
        r'sort_keys',
        # -- pydantic v2 removed allow_mutation --
        r'allow_mutation',
        # -- json_db / model internals rewrites --
        r'if args:',
        r'if extra is',
        r'annotation\s*=',
        r'inner_type',
        r'and\s+\w+\s+is not None',
        r'\*\*extra',
        r'media\s*=\s*\[',  # list comprehension reformatting
        # -- validator body assignment (status_icon, etc.) --
        r'values\[',
        # -- multi-type optional defaults with union syntax --
        r':\s*[\w.\[\]\s|]+None\s*$',  # v1: field: str | list[str] | None
        r':\s*[\w.\[\]\s|]+None\s*=\s*None',  # v2: field: str | list[str] | None = None
        # -- json_db refactored conditionals --
        r'and not is_embedded',
        r'is_embedded',
        r'json_db_embedded',
        r'json_db_index',
        r'unserialized\[',
        # -- f-string / error message reformatting --
        r"f'backoff_",
    ]
]

# Files that are expected to always differ.
EXPECTED_DIVERGENCE = {
    'tie/basic/manifest.json',
    'tie/basic/requirements.txt',
}

# Lines that are never meaningful (blank, comments, docstrings, section dividers).
NOISE = re.compile(
    r'^[+-]\s*$'  # blank added/removed lines
    r'|^[+-]\s*#'  # comment lines
    r'|^[+-]\s*"""'  # docstring delimiters
    r'|^[+-]\s*---'  # section dividers
    r'|^[+-]\s*Model (Config|Definition|Configuration)'  # docstring text
    r'|^[+-]\s*if TYPE_CHECKING'  # typing guard blocks
    r'|^[+-]\s*\.\.\.'  # ellipsis (abstract methods)
    r'|^[+-]\s*\)'  # closing parens (reformatting)
    r'|^[+-]\s*\]'  # closing brackets
    r'|^[+-]\s*\}'  # closing braces
    r'|^[+-]\s*for\s'  # for loops (often reformatted)
    r'|^[+-]\s*return\s'  # return statements (often reformatted)
)


def is_pydantic_line(line: str) -> bool:
    """Return True if a diff line is explainable by pydantic v1/v2 migration."""
    stripped = line.lstrip('+-').strip()
    if not stripped:
        return True  # blank line changes are noise
    return any(p.search(stripped) for p in PYDANTIC_PATTERNS)


def is_noise(line: str) -> bool:
    """Return True if the line is a comment, blank, or docstring change."""
    return bool(NOISE.match(line))


def run_diff(branch_a: str, branch_b: str) -> str:
    """Run git diff between two branches for tie/basic/."""
    result = subprocess.run(  # nosec B603, B607
        ['git', 'diff', f'{branch_a}..{branch_b}', '--unified=0', '--', 'tie/basic/'],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def parse_diff(diff_output: str) -> dict[str, list[str]]:
    """Parse unified diff and return files with unexplained lines."""
    divergent: dict[str, list[str]] = {}
    current_file = None

    for line in diff_output.splitlines():
        if line.startswith('diff --git'):
            # Extract file path: diff --git a/path b/path
            parts = line.split(' b/')
            current_file = parts[-1] if len(parts) > 1 else None
            continue

        if current_file and current_file in EXPECTED_DIVERGENCE:
            continue

        # Only look at added/removed lines (not headers, context, etc.)
        if not line.startswith(('+', '-')):
            continue
        # Skip diff file headers
        if line.startswith(('+++', '---')):
            continue

        if is_noise(line):
            continue

        if current_file and not is_pydantic_line(line):
            if current_file not in divergent:
                divergent[current_file] = []
            divergent[current_file].append(line)

    return divergent


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]

    branch_a = args[0] if len(args) > 0 else 'v2'
    branch_b = args[1] if len(args) > 1 else 'v3'

    print(f'Checking branch sync: {branch_a}..{branch_b}')
    print('=' * 50)

    diff_output = run_diff(branch_a, branch_b)
    if not diff_output:
        print('No differences found.')
        return 0

    # Count total files changed
    total_files = sum(
        1 for diff_line in diff_output.splitlines() if diff_line.startswith('diff --git')
    )

    divergent = parse_diff(diff_output)

    # Count expected divergence files
    expected_count = sum(
        1
        for diff_line in diff_output.splitlines()
        if diff_line.startswith('diff --git') and any(e in diff_line for e in EXPECTED_DIVERGENCE)
    )

    clean_count = total_files - expected_count - len(divergent)

    print(f'  {clean_count} files — pydantic-only changes')
    print(f'  {expected_count} files — expected divergence (manifest, requirements)')

    if not divergent:
        print('\nBranches are in sync (pydantic differences only).')
        return 0

    print(f'\n  *** {len(divergent)} files with unexpected divergence ***\n')

    for filepath, lines in sorted(divergent.items()):
        print(f'  {filepath}')
        # Show up to 8 lines per file to avoid noise
        for line in lines[:8]:
            print(f'    {line}')
        if len(lines) > 8:
            print(f'    ... and {len(lines) - 8} more lines')
        print()

    return 1


if __name__ == '__main__':
    sys.exit(main())
