#!/usr/bin/env python3
"""Post-commit hook that rebuilds manifest.json files when template files change.

Detects which template directories were affected by the last commit and
regenerates their manifests using ``build_all_manifests.py``.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Guard against recursive invocation — build() sets this env var before
# shelling out to build_all_manifests.py, which itself triggers a commit
# that would re-invoke this hook.
if os.environ.get("MANIFEST_HOOK_DISABLED") == "1":
    sys.exit(0)


def run(cmd, *, cwd=None, timeout=None, check=True, capture_output=False, env=None):
    return subprocess.run(
        cmd,
        cwd=cwd,
        timeout=timeout,
        check=check,
        text=True,
        capture_output=capture_output,
        env=env,
    )


class ManifestBuilder:

    def __init__(self):
        self.log_path = Path(self.repo_path / '.git' / 'manifest-hook.log')
        self.log_path.write_text('', encoding='utf-8')
        self.skip_message = "[skip-manifest]"

    @property
    def repo_path(self) -> Path:
        # git rev-parse --show-toplevel returns the absolute path to the repo root
        # e.g. "/Users/you/projects/tcex-app-templates"
        out = run(["git", "rev-parse", "--show-toplevel"], capture_output=True).stdout.strip()
        return Path(out)

    def log(self, msg: str) -> None:
        """Log a message to the hook log file and stdout."""
        try:
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(msg + "\n")
        except Exception:
            pass
        print(msg, flush=True)

    @property
    def _last_commit_message(self):
        # git log -1 --pretty=%B returns just the commit message body
        # e.g. "fix: update app.py logic\n"
        return run(
            ["git", "log", "-1", "--pretty=%B"], capture_output=True, cwd=self.repo_path
        ).stdout

    def _find_template_dirs(self) -> set[str]:
        """Return repo-relative POSIX paths of all directories containing template.yaml."""
        dirs: set[str] = set()
        for root, _dirnames, filenames in os.walk(self.repo_path):
            if 'template.yaml' in filenames:
                rel = Path(root).relative_to(self.repo_path).as_posix()
                dirs.add(rel)
        return dirs

    def _touched_files(self) -> list[str]:
        """Return list of files changed in the last commit."""
        # git diff-tree lists files changed in a commit without diffing the working tree.
        # --no-commit-id suppresses the commit SHA line, --name-only gives just paths,
        # -r recurses into subtrees so we get full file paths.
        # e.g. "playbook/basic/app.py\nplaybook/basic/run.py\n"
        out = run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            capture_output=True,
            cwd=self.repo_path,
        ).stdout
        return [p.strip() for p in out.splitlines() if p.strip()]

    def _affected_template_dirs(self) -> set[str]:
        """Return template dirs that had non-manifest files modified in the last commit."""
        template_dirs = self._find_template_dirs()
        touched = self._touched_files()

        affected: set[str] = set()
        for filepath in touched:
            # manifest.json files are what we generate — don't treat them as triggers
            if filepath.endswith('/manifest.json') or filepath == 'manifest.json':
                continue
            # check if this file lives inside any known template directory
            for tdir in template_dirs:
                if filepath.startswith(tdir + '/'):
                    affected.add(tdir)

        return affected

    def get_affected_dirs(self) -> set[str]:
        """Return affected dirs, or empty set if processing should be skipped."""
        if self.skip_message in self._last_commit_message:
            self.log('[manifest] skipping due to skip tag in commit message')
            return set()
        affected = self._affected_template_dirs()
        self.log(f'[manifest] affected template dirs: {sorted(affected) if affected else "none"}')
        return affected

    def build(self, dirs: set[str]):
        self.log(f'[manifest] rebuilding manifests for: {sorted(dirs)}')
        # Set MANIFEST_HOOK_DISABLED so the child commit (in commit()) doesn't
        # re-trigger this hook in an infinite loop.
        env = os.environ.copy()
        env["MANIFEST_HOOK_DISABLED"] = "1"
        # Pass only the affected dirs so build_all_manifests.py rebuilds just those
        run(
            [sys.executable, "scripts/build_all_manifests.py", "--root", "."] + sorted(dirs),
            cwd=self.repo_path,
            timeout=120,
            env=env,
        )

    def add_manifests(self, dirs: set[str]):
        """Stage manifest.json files for the affected dirs only."""
        self.log('[manifest] staging updated manifests')
        manifests = [f'{d}/manifest.json' for d in sorted(dirs)]
        run(["git", "add", "--"] + manifests, cwd=self.repo_path)

    def commit(self):
        """Commit staged manifest changes (no-op if nothing staged)."""
        # git diff --cached --quiet exits 0 if nothing is staged, 1 if there are
        # staged changes. We use check=False so exit code 1 doesn't raise.
        result = run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=self.repo_path,
            check=False,
        )
        if result.returncode == 0:
            self.log('[manifest] no manifest changes to commit')
            return

        self.log('[manifest] committing updated manifests')
        # core.hooksPath=/dev/null disables all hooks for this commit so we
        # don't re-trigger the post-commit hook recursively.
        run(
            [
                "git",
                "-c",
                "core.hooksPath=/dev/null",
                "commit",
                "-m",
                f"chore: update manifests {self.skip_message}",
                "--quiet",
            ],
            cwd=self.repo_path,
        )


if __name__ == "__main__":
    manifest_builder = ManifestBuilder()
    try:
        affected = manifest_builder.get_affected_dirs()
        if not affected:
            sys.exit(0)
        manifest_builder.build(affected)
        manifest_builder.add_manifests(affected)
        manifest_builder.commit()
    except Exception as e:
        manifest_builder.log(f'[manifest] error: {e}')
        sys.exit(1)
