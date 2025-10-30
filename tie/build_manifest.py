#!/usr/bin/env python3
"""build_manifest.py

- Loads `template.yaml` from the input template and recursively from parent templates.
- Parent/child precedence: earlier parents < later parents < child.
- Expands directories recursively (skips .git, __pycache__, .venv, node_modules, .nx).
- Keys are POSIX relative paths from --root, then the first path segment is removed.
- Writes <input_dir>/manifest.json.
- Same CLI, logging, and print messages for collection and consolidated counts.
"""

from __future__ import annotations

# standard library
import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

try:
    # third-party
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    print(
        'ERROR: PyYAML is required. Install with:\n\n  pip install pyyaml\n',
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------
# Data model
# ---------------------------------


@dataclass(frozen=True)
class TemplateInfo:
    """Information about a template directory and its parsed config."""

    dir_path: Path
    config: dict


# ---------------------------------
# YAML / Template resolution
# ---------------------------------


class TemplateResolver:
    """Resolves template inheritance and loads template.yaml files."""

    def __init__(self, root_dir: Path) -> None:
        """Initialize with the templates root directory."""
        self.root_dir = root_dir.resolve()

    def load_template_yaml(self, dir_path: Path) -> TemplateInfo:
        """Load and parse `template.yaml` from a template directory."""
        yaml_path = dir_path / 'template.yaml'
        if not yaml_path.is_file():
            raise SystemExit(f'Missing template.yaml: {yaml_path}')

        try:
            with yaml_path.open('r', encoding='utf-8') as fh:
                data = yaml.safe_load(fh) or {}
        except Exception as e:
            raise SystemExit(f'Failed to parse {yaml_path}: {e}')

        return TemplateInfo(dir_path=dir_path, config=data)

    def resolve(self, input_dir: Path) -> list[Path]:
        """Return template directories in precedence order."""
        acc: list[Path] = []
        self._resolve_chain(input_dir.resolve(), [], acc)
        return acc

    def _resolve_chain(self, template_dir: Path, stack: list[Path], acc: list[Path]) -> None:
        """Depth-first resolution.

        Earlier parents first, later parents next, then the current template last.
        Detects cycles using `stack`.
        """
        info = self.load_template_yaml(template_dir)
        parents: Sequence[str] = info.config.get('template_parents', []) or []

        # Cycle detection
        if template_dir in stack:
            cycle = ' -> '.join(p.as_posix() for p in (*stack, template_dir))
            raise SystemExit(f'Cycle detected in template_parents: {cycle}')

        stack.append(template_dir)
        try:
            for parent_name in parents:
                parent_dir = (self.root_dir / parent_name).resolve()
                if not parent_dir.is_dir():
                    raise SystemExit(f'Parent template directory not found: {parent_dir}')
                self._resolve_chain(parent_dir, stack, acc)
            acc.append(template_dir)
        finally:
            stack.pop()


# ---------------------------------
# File discovery
# ---------------------------------


class FileExpander:
    """Expands template file entries to concrete file paths."""

    EXCLUDED_DIRS = {'.git', '__pycache__', '.venv', 'node_modules', '.nx'}

    def iter_template_files(
        self, template_dir: Path, relative_paths: Sequence[str]
    ) -> Iterator[Path]:
        """Yield absolute file Paths for each entry.

          - If entry is a file: yield it.
          - If entry is a directory: recursively yield all contained files.
        Skips any excluded directories.
        """
        for rel in relative_paths:
            src = (template_dir / rel).resolve()
            if src.is_file():
                yield src
            elif src.is_dir():
                if src.name in self.EXCLUDED_DIRS:
                    continue
                for root, dirs, files in os.walk(src, topdown=True):
                    dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS]
                    for fn in files:
                        yield Path(root) / fn
            else:
                print(f'Referenced path does not exist (skipping): {src}')


# ---------------------------------
# Hashing / Git helpers
# ---------------------------------


class GitHelper:
    """Encapsulates Git root resolution and last-commit lookups."""

    def __init__(self, start_dir: Path) -> None:
        """Initialize with the start directory to find the Git repo root."""
        self.repo_root: Path | None = self._git_repo_root(start_dir)

    def _git_repo_root(self, start_dir: Path) -> Path | None:
        """Return the Git repository root, or None if not in a repo."""
        try:
            out = subprocess.check_output(
                ['git', '-C', str(start_dir), 'rev-parse', '--show-toplevel'],
                text=True,
                stderr=subprocess.STDOUT,
            )
            return Path(out.strip())
        except Exception:
            return None

    def last_commit(self, file_path: Path) -> str | None:
        """Return last commit SHA for file_path using local Git, or None if unavailable."""
        if not self.repo_root:
            return None

        try:
            rel = file_path.resolve().relative_to(self.repo_root.resolve())
        except Exception:
            return None

        try:
            out = subprocess.check_output(
                [
                    'git',
                    '-C',
                    str(self.repo_root),
                    'log',
                    '-n',
                    '1',
                    '--pretty=format:%H',
                    '--',
                    str(rel),
                ],
                text=True,
                stderr=subprocess.STDOUT,
            )
            sha = out.strip()
            return sha or None
        except Exception:
            return None


class HashHelper:
    """Encapsulates file hashing helpers."""

    @staticmethod
    def sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
        """Compute SHA-256 hash of a file."""
        h = hashlib.sha256()
        with path.open('rb') as fh:
            for chunk in iter(lambda: fh.read(chunk_size), b''):
                h.update(chunk)
        return h.hexdigest()


# ---------------------------------
# Manifest builder
# ---------------------------------


class ManifestBuilder:
    """Builds the manifest map.

    key   -> POSIX relative path from root_dir (then strips first segment)
    value -> {"sha256": <sha256>, "last_commit": <sha or None>, "template_path": <key>}
    """

    def __init__(self, root_dir: Path, git: GitHelper) -> None:
        """Initialize with root_dir and GitHelper."""
        self.root_dir = root_dir.resolve()
        self.git = git

    def build(self, files: list[Path]) -> dict[str, dict[str, str | None]]:
        """Build the manifest from the given list of absolute file Paths."""
        # 1) Build initial manifest keyed by POSIX path relative to root_dir
        raw_manifest: dict[str, dict[str, str | None]] = {}
        for abs_path in files:
            try:
                key_path = abs_path.resolve().relative_to(self.root_dir)
            except Exception:
                print(f'File is outside root_dir, skipping: {abs_path}')
                continue

            key = key_path.as_posix()
            sha256 = HashHelper.sha256(abs_path)
            last_commit = self.git.last_commit(abs_path)

            raw_manifest[key] = {
                'sha256': sha256,
                'last_commit': last_commit,
                'template_path': key,
            }

        # 2) Stable order by key
        ordered = {k: raw_manifest[k] for k in sorted(raw_manifest.keys())}

        # 3) Remove the first directory from each key in the manifest (preserve original behavior)
        trimmed = {
            '/'.join(k.split('/')[1:]): v for k, v in ordered.items() if len(k.split('/')) > 1
        }
        return trimmed


# ---------------------------------
# Application Orchestrator
# ---------------------------------


class BuildManifestApp:
    """High-level application that wires all components and preserves CLI behavior."""

    def __init__(self, args: argparse.Namespace) -> None:
        """Initialize with parsed arguments."""
        self.args = args
        self.root_dir = Path(args.root).resolve()
        self.input_dir = Path(args.input_dir).resolve()

        self.resolver = TemplateResolver(self.root_dir)
        self.expander = FileExpander()
        self.git = GitHelper(self.root_dir)
        self.manifest_builder = ManifestBuilder(self.root_dir, self.git)

    def run(self) -> None:
        """Execute the manifest building process."""
        # Validate input template.yaml exists (preserve exit behavior)
        tmpl_yaml = self.input_dir / 'template.yaml'
        if not tmpl_yaml.is_file():
            raise SystemExit(f'Missing template.yaml: {tmpl_yaml}')

        # Resolve template chain (precedence info only for logging)
        print(f'Resolving templates from: {self.input_dir} (root={self.root_dir})')
        chain = self.resolver.resolve(self.input_dir)
        print(f'Template order (low -> high precedence): {" -> ".join(p.name for p in chain)}')

        # Consolidate files with precedence:
        # earlier parents first, later parents next, child last
        # later entries override earlier ones
        consolidated: dict[str, Path] = {}

        for tmpl_dir in chain:
            info = self.resolver.load_template_yaml(tmpl_dir)
            rel_paths: Sequence[str] = info.config.get('template_files', []) or []

            print(f'Collecting from {tmpl_dir}: {len(rel_paths)} entries')
            for abs_file in self.expander.iter_template_files(tmpl_dir, rel_paths):
                try:
                    # Manifest keys must be POSIX paths relative to root_dir
                    key = abs_file.resolve().relative_to(self.root_dir.resolve()).as_posix()
                except Exception:
                    print(f'Skipping file outside root_dir: {abs_file}')
                    continue
                # Precedence: later templates overwrite the same key
                consolidated[key] = abs_file

        print('Consolidated files:', len(consolidated))

        # Stable list of files based on sorted keys
        files_ordered = [consolidated[k] for k in sorted(consolidated.keys())]

        # Build manifest map (includes SHA-256 + last_commit) and trims first path segment
        manifest = self.manifest_builder.build(files_ordered)

        # Write manifest.json inside input directory
        output_path = self.input_dir / 'manifest.json'
        output_path.write_text(json.dumps(manifest, indent=4), encoding='utf-8')
        print(f'Wrote {output_path} ({len(manifest)} entries)')


# ---------------------------------
# CLI
# ---------------------------------


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    ap = argparse.ArgumentParser(
        description='Build manifest.json for a template directory and its parent templates.'
    )
    ap.add_argument('input_dir', help='Child template directory (e.g., tcv)')
    ap.add_argument(
        '--root', default='.', help='Templates root (default: current working directory)'
    )
    return ap.parse_args(argv)


def main() -> None:
    """Entry point."""
    args = parse_args()
    BuildManifestApp(args).run()


if __name__ == '__main__':
    main()

# -------------------------------
# Usage
# -------------------------------
# Example:
#   python build_manifest.py tcv
#   python build_manifest.py tcv --root .
#
# Output is written to: tcv/manifest.json
