"""TIE-specific profile models for pipeline test cases."""
from __future__ import annotations

import fnmatch
import gzip
import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import jmespath as _jmespath
from pydantic import BaseModel, Field

from tcex_testing.checks import CheckLike, ScopedCheck
from tcex_testing.profile import Expected, FetchExpected, FetchRecord, Stage

if TYPE_CHECKING:
    from tcex_testing.apps.tie.base import TieTestCase


class Record(BaseModel):
    """Describes a record to extract from pipeline stage output (Download, Convert).

    key:      Label — referenced in checks via Check.on(key).
    file:     Glob pattern relative to the stage output_dir (e.g. 'sightings_*.json.gz').
    jmespath: JMESPath expression applied to each matched file's parsed content.
              Use '$' to keep the full document, '$.data[*]' to extract a nested list.
    """

    key: str
    file: str
    jmespath: str


class UploadExpected(FetchExpected):
    """Expected assertions for the Upload pipeline stage.

    records: TC API fetches to run after upload. Each FetchRecord queries the TC
             platform and stores results (a list of TC objects) under record.key.
    checks:  Assertions against fetched records — use Check.on(key) / Check.all() /
             Check.any() / Check.count() / or plain Callables.
    """

    records: list[FetchRecord] = Field(default_factory=list)
    checks: list[CheckLike] = Field(default_factory=list)

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


class PipelineExpected(Expected):
    """Expected output for a pipeline stage that writes files (Download, Convert).

    records:  Data to extract from stage output. Each Record globs files in the stage
              output_dir, loads and parses them, applies jmespath, and stores the result
              under record.key for use in checks.

    checks:   Assertions run after all records are resolved. Each entry is either:
              - ScopedCheck  — created by Check.on(key) / Check.all() / Check.any() /
                               Check.count()
              - Callable     — receives the full resolved records dict; use for custom logic
    """

    records: list[Record] = Field(default_factory=list)
    checks: list[CheckLike] = Field(default_factory=list)

    def assert_exit_code(self, result: Any) -> None:
        pass  # Pipeline stages (Download, Convert) don't produce exit codes.

    def assert_exit_message(self, result: Any) -> None:
        pass  # Pipeline stages (Download, Convert) don't produce exit messages.

    def fetch_records(self, result: Any) -> dict:
        """Extract records from stage output files using glob + jmespath."""
        output_dir: Path = result.output_dir
        resolved: dict[str, Any] = {}

        for record in self.records:
            # rglob, not iterdir: TIE Download tasks commonly write per-type
            # subdirectories under the stage output dir. iterdir() yielded those
            # directories, fnmatch'd their names against '*.json.gz', matched nothing,
            # and left this key as an empty list — a pipeline that produced hundreds of
            # files looked like one that produced none. Matches `DownloadResult.files`,
            # which already uses rglob.
            matched = sorted(
                f
                for f in output_dir.rglob('*')
                if f.is_file() and fnmatch.fnmatch(f.name, record.file)
            )
            items: list[Any] = []
            for path in matched:
                if path.suffix == '.gz':
                    with gzip.open(path, 'rt', encoding='utf-8') as fh:
                        content = json.load(fh)
                else:
                    with path.open(encoding='utf-8') as fh:
                        content = json.load(fh)
                extracted = _jmespath.search(record.jmespath, content)
                if isinstance(extracted, list):
                    items.extend(extracted)
                elif extracted is not None:
                    items.append(extracted)
            resolved[record.key] = items

        return resolved

    def assert_result(self, result: Any, resolved: dict | None = None) -> None:
        super().assert_result(result, resolved)
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


class PipelineTask(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    task_cls: type
    expected: Expected = Field(default_factory=PipelineExpected)
    before: Callable[[TieTestCase], None] | list[Callable[[TieTestCase], None]] = Field(default=lambda *_: None)
    after: Callable[[TieTestCase, Any], None] | list[Callable[[TieTestCase, Any], None]] = Field(default=lambda *_: None)


class Profile(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    job_request: Any  # JobRequestModel — app-specific, saved to DB by run()
    pipeline: list[PipelineTask]
    stage: Stage = Field(default_factory=Stage)
    environments: list[str] = Field(default_factory=list)
