#!/usr/bin/env python3
"""build_all_manifests.py

Generate a per-directory manifest.json for every template directory
(any directory containing a template.yaml).  Each manifest contains
entries only for files in that directory — the CLI merges parent
manifests at runtime.

Usage:
    python scripts/build_all_manifests.py                       # rebuild all
    python scripts/build_all_manifests.py playbook/basic        # rebuild one
    python scripts/build_all_manifests.py --root /path/to/repo  # explicit root
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Sequence

# Files/dirs to exclude from manifests.
# template.yaml and manifest.json are metadata, not deliverable template files.
EXCLUDED_FILES = {'template.yaml', 'manifest.json', '.DS_Store'}
EXCLUDED_DIRS = {'.git', '__pycache__', '.venv', 'node_modules', '.nx'}


# ---------------------------------------------------------------------------
# Helpers (adapted from tie/build_manifest.py)
# ---------------------------------------------------------------------------


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b''):
            h.update(chunk)
    return h.hexdigest()


def git_repo_root(start_dir: Path) -> Path | None:
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


def build_commit_map(repo_root: Path) -> dict[str, str]:
    """Build a map of repo-relative POSIX path -> most recent commit SHA.

    Parses the full ``git log`` output in one pass.  The log alternates between
    commit SHA lines (40-char hex) and the file paths modified in that commit.
    We record only the *first* SHA seen for each path (= the most recent commit
    that touched it).

    git log --format=%H --name-only produces output like::

        abc123...  (40-char commit SHA)
        playbook/basic/app.py
        playbook/basic/run.py

        def456...  (older commit SHA)
        playbook/basic/app.py
        _app_common/setup.cfg

    Result: {"playbook/basic/app.py": "abc123...", "playbook/basic/run.py": "abc123...",
             "_app_common/setup.cfg": "def456..."}
    (app.py maps to abc123 because that's the newest commit — def456 is ignored)
    """
    try:
        out = subprocess.check_output(
            ['git', '-C', str(repo_root), 'log', '--format=%H', '--name-only'],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except Exception:
        return {}

    commit_map: dict[str, str] = {}
    current_sha: str | None = None
    for line in out.splitlines():
        if not line:
            continue
        # Detect commit SHA lines: exactly 40 hex chars, no path separators or dots
        if len(line) == 40 and os.sep not in line and '.' not in line:
            try:
                int(line, 16)
                current_sha = line
                continue
            except ValueError:
                pass
        # Everything else is a file path — only keep the first occurrence
        # (first = most recent, since git log is newest-first)
        if current_sha and line not in commit_map:
            commit_map[line] = current_sha

    return commit_map


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def find_template_dirs(root: Path) -> list[Path]:
    """Find all directories under *root* that contain a template.yaml."""
    dirs: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        if 'template.yaml' in filenames:
            dirs.append(Path(dirpath))
    return sorted(dirs)


def collect_files(template_dir: Path) -> list[Path]:
    """Return all files in *template_dir* that belong in the manifest.

    Walks the directory recursively, skipping excluded dirs/files.
    The returned list is sorted so manifest output is deterministic.
    """
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(template_dir, topdown=True):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for fn in filenames:
            if fn in EXCLUDED_FILES:
                continue
            files.append(Path(dirpath) / fn)
    return sorted(files)


# ---------------------------------------------------------------------------
# Manifest building
# ---------------------------------------------------------------------------


def build_manifest(
    template_dir: Path,
    root: Path,
    commit_map: dict[str, str],
    repo_root: Path | None,
) -> dict[str, dict]:
    """Build a manifest dict for a single template directory.

    Keys are file paths relative to the template dir, with ``gitignore``
    renamed to ``.gitignore`` to match CLI behaviour.  If both ``gitignore``
    and ``.gitignore`` exist (e.g. in ``_app_common``), the ``gitignore``
    entry wins because it sorts after ``.gitignore`` and overwrites it.
    This is intentional — ``gitignore`` is the template file that gets
    delivered to user projects; ``.gitignore`` is just the repo-level ignore.
    """
    files = collect_files(template_dir)
    manifest: dict[str, dict] = {}

    # dir_prefix is used for the template_path field to record which
    # template directory a file originally came from (provenance).
    # e.g. "playbook/basic" or "_app_common"
    try:
        dir_prefix = template_dir.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        dir_prefix = template_dir.name

    for abs_path in files:
        rel = abs_path.relative_to(template_dir)

        # Template dirs store .gitignore as "gitignore" (without the dot) to
        # avoid git treating it as a real ignore file.  Rename it in the
        # manifest key to match what the CLI delivers to user projects.
        parts = list(rel.parts)
        if parts[-1] == 'gitignore':
            parts[-1] = '.gitignore'
            rel = Path(*parts)

        key = rel.as_posix()
        file_hash = sha256_file(abs_path)

        # Look up the git commit SHA that last modified this file, using the
        # pre-built commit map (keyed by repo-relative POSIX path).
        last_commit: str | None = None
        if repo_root:
            try:
                repo_rel = abs_path.resolve().relative_to(repo_root.resolve()).as_posix()
                last_commit = commit_map.get(repo_rel)
            except ValueError:
                pass

        manifest[key] = {
            'sha256': file_hash,
            'last_commit': last_commit or '',
            'template_path': f'{dir_prefix}/{key}',
        }

    # stable key ordering for deterministic output
    return {k: manifest[k] for k in sorted(manifest)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> None:
    """Entry point."""
    ap = argparse.ArgumentParser(
        description='Generate manifest.json for template directories.'
    )
    ap.add_argument(
        '--root',
        default='.',
        help='Repository root directory (default: current working directory)',
    )
    ap.add_argument(
        'dirs',
        nargs='*',
        help='Specific template directories to rebuild (relative to root). '
        'If omitted, rebuilds all template directories.',
    )
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    repo_root = git_repo_root(root)

    print(f'Root: {root}')
    print(f'Git repo: {repo_root or "not a git repo"}')

    # Build the commit map once upfront. This is the most expensive operation
    # (parses the full git log), but it's amortised across all template dirs.
    commit_map: dict[str, str] = {}
    if repo_root:
        print('Building git commit map ...')
        commit_map = build_commit_map(repo_root)
        print(f'  {len(commit_map)} file entries')

    if args.dirs:
        template_dirs = [root / d for d in args.dirs]
    else:
        template_dirs = find_template_dirs(root)

    print(f'Building manifests for {len(template_dirs)} directories\n')

    for tdir in template_dirs:
        rel = tdir.relative_to(root)
        manifest = build_manifest(tdir, root, commit_map, repo_root)
        out_path = tdir / 'manifest.json'
        out_path.write_text(json.dumps(manifest, indent=4) + '\n', encoding='utf-8')
        print(f'  {rel}/manifest.json  ({len(manifest)} entries)')

    print(f'\nDone — wrote {len(template_dirs)} manifests.')


if __name__ == '__main__':
    main()
