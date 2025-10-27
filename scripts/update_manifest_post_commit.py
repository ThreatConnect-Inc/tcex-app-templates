#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

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
        out = run(["git", "rev-parse", "--show-toplevel"], capture_output=True).stdout.strip()
        return Path(out)

    def log(self, msg: str) -> None:
        """Log a message to the hook log file."""
        try:
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(msg + "\n")
        except Exception:
            pass
        print(msg, flush=True)

    @property
    def _last_commit_message(self):
        return run(
            ["git", "log", "-1", "--pretty=%B"], capture_output=True, cwd=self.repo_path
        ).stdout

    @property
    def _template_files_touched(self) -> bool:
        self.log('[manifest] checking for template file changes in last commit')
        out = run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            capture_output=True,
            cwd=self.repo_path,
        ).stdout
        prefix = 'tie/'
        return any(p.strip().startswith(prefix) for p in out.splitlines())

    def should_process(self):
        if self.skip_message in self._last_commit_message:
            self.log('[manifest] skipping due to skip tag in commit message')
            return False
        should_process = self._template_files_touched
        self.log(f'[manifest] template files touched: {should_process}')
        return should_process

    def build(self):
        prev_cwd = os.getcwd()
        try:
            os.chdir(self.repo_path / 'tie')
            self.log(f'[manifest] building updated manifest, cwd={os.getcwd()}')

            env = os.environ.copy()
            env["MANIFEST_HOOK_DISABLED"] = "1"
            run(
                [sys.executable, "build_manifest.py", "tcv"],
                cwd=os.getcwd(),
                timeout=120,
                env=env,
            )
        finally:
            os.chdir(prev_cwd)

    def add_manifest(self):
        self.log('[manifest] staging updated manifest')
        run(["git", "add", "--", 'tie/tcv/manifest.json'], cwd=self.repo_path)

    def commit(self):
        self.log('[manifest] committing updated manifest')
        run(
            [
                "git",
                "-c",
                "core.hooksPath=/dev/null",
                "commit",
                "-m",
                f"chore: update manifest {self.skip_message}",
                "--quiet",
                "--",  # end of options, commit only this path
                'tie/tcv/manifest.json',
            ],
            cwd=self.repo_path,
        )


if __name__ == "__main__":
    manifest_builder = ManifestBuilder()
    try:
        if manifest_builder.should_process() is False:
            sys.exit(0)
        manifest_builder.build()
        manifest_builder.add_manifest()
        manifest_builder.commit()
    except Exception as e:
        sys.exit(1, str(e))
