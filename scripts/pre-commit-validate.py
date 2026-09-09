#!/usr/bin/env python3
"""Pre-commit hook that validates TC Exchange app_spec.yml before committing.

Runs registered validators in order. Validators may auto-fix issues and stage
changes; if they do, the fix is included in the current commit. Validators that
cannot auto-fix will print an error and exit 1 to abort the commit.

Requires: pyyaml>=6.0
"""

from __future__ import annotations

import re
import subprocess  # nosec B404
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml

APP_SPEC = Path('app_spec.yml')

GREEN = '\033[0;32m'
YELLOW = '\033[0;33m'
RED = '\033[0;31m'
NC = '\033[0m'


def _ok(msg: str) -> None:
    print(f'{GREEN}[ok]{NC} {msg}', flush=True)


def _warn(msg: str) -> None:
    print(f'{YELLOW}[warn]{NC} {msg}', flush=True)


def _error(msg: str) -> None:
    print(f'{RED}[error]{NC} {msg}', flush=True)


def _run(
    cmd: list[str], *, check: bool = True, capture: bool = False
) -> subprocess.CompletedProcess:
    return subprocess.run(  # nosec B603
        cmd,
        text=True,
        check=check,
        capture_output=capture,
    )


def _stage(path: str) -> None:
    _run(['git', 'add', '--', path])


# ---------------------------------------------------------------------------
# Validator base
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    passed: bool
    fixed: bool = False
    messages: list[str] = field(default_factory=list)


class Validator(ABC):
    """Base class for all pre-commit validators."""

    name: str = 'validator'

    @abstractmethod
    def run(self, spec_text: str, spec_data: dict) -> ValidationResult:
        """Validate app_spec.yml.

        Args:
            spec_text: Raw file content (used for in-place auto-fixes).
            spec_data: Parsed YAML data (use for reads).

        Returns a ValidationResult. If ``passed`` is False and ``fixed`` is
        False, the commit is aborted.
        """
        ...


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


class LabelsValidator(Validator):
    """Fail if app_spec.yml has fewer than 1 label."""

    name = 'labels'

    def run(self, spec_text: str, spec_data: dict) -> ValidationResult:  # noqa: ARG002
        labels = spec_data.get('labels') or []
        if not labels:
            return ValidationResult(
                passed=False,
                messages=['app_spec.yml has no labels. Add at least one label.'],
            )
        return ValidationResult(passed=True)


class NewLabelWarningValidator(Validator):
    """Warn (non-blocking) if labels were added that did not exist on main."""

    name = 'new-label-warning'

    def run(self, spec_text: str, spec_data: dict) -> ValidationResult:  # noqa: ARG002
        result = _run(
            ['git', 'show', 'origin/main:app_spec.yml'],
            check=False,
            capture=True,
        )
        if result.returncode != 0:
            # Can't compare — no main branch or file doesn't exist there yet
            return ValidationResult(passed=True)

        main_data = yaml.safe_load(result.stdout) or {}
        current_labels = set(spec_data.get('labels') or [])
        main_labels = set(main_data.get('labels') or [])
        new_labels = current_labels - main_labels

        messages = [f'New label(s) added: {sorted(new_labels)}'] if new_labels else []
        return ValidationResult(passed=True, messages=messages)


class ReleaseDateValidator(Validator):
    """Ensure the latest release note has today's date.

    If the date is missing or stale, auto-updates app_spec.yml in place and
    stages the change so the fix is included in the current commit.

    The version field in app_spec.yml is a string: "1.0.13" or "1.0.13 (2026-04-21)".
    YAML parsing gives us the version string; string replacement handles the write-back
    to avoid reformatting the entire file.
    """

    name = 'release-date'

    _DATE_RE = re.compile(r'\(([\dx]{4}-[\dx]{2}-[\dx]{2})\)$')

    def run(self, spec_text: str, spec_data: dict) -> ValidationResult:
        release_notes = spec_data.get('releaseNotes') or []
        if not release_notes:
            return ValidationResult(
                passed=False,
                messages=['app_spec.yml has no releaseNotes.'],
            )

        latest = release_notes[0]
        version_str = str(latest.get('version', ''))
        if not version_str:
            return ValidationResult(
                passed=False,
                messages=['Latest release note has no version field.'],
            )

        today = datetime.now(tz=UTC).date().isoformat()
        date_match = self._DATE_RE.search(version_str)
        existing_date = date_match.group(1) if date_match else None

        if existing_date == today:
            return ValidationResult(passed=True)

        # Auto-fix: replace the version string in the raw file text
        if existing_date:
            new_version_str = self._DATE_RE.sub(f'({today})', version_str)
        else:
            new_version_str = f'{version_str} ({today})'

        updated = spec_text.replace(
            f'version: {version_str}',
            f'version: {new_version_str}',
            1,
        )
        APP_SPEC.write_text(updated, encoding='utf-8')
        _stage(str(APP_SPEC))

        action = 'updated' if existing_date else 'added'
        return ValidationResult(
            passed=True,
            fixed=True,
            messages=[f'Release date {action} for {version_str}: {today}'],
        )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

VALIDATORS: list[Validator] = [
    LabelsValidator(),
    NewLabelWarningValidator(),
    ReleaseDateValidator(),
]


def main() -> None:
    if not APP_SPEC.exists():
        # Not a TC Exchange app repo — skip silently
        sys.exit(0)

    spec_text = APP_SPEC.read_text(encoding='utf-8')
    spec_data: dict = yaml.safe_load(spec_text) or {}

    failed = False
    for validator in VALIDATORS:
        result = validator.run(spec_text, spec_data)

        for msg in result.messages:
            if not result.passed:
                _error(f'[{validator.name}] {msg}')
            elif result.fixed:
                _ok(f'[{validator.name}] {msg}')
            else:
                _warn(f'[{validator.name}] {msg}')

        if not result.passed:
            failed = True

        # Re-read after any auto-fix so subsequent validators see updated content
        if result.fixed:
            spec_text = APP_SPEC.read_text(encoding='utf-8')
            spec_data = yaml.safe_load(spec_text) or {}

    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
