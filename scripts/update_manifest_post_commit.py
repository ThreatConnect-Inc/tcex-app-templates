#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def run(cmd, *, cwd=None, timeout=None, check=True, capture_output=False):
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        timeout=timeout,
        check=check,
        text=True,
        capture_output=capture_output,
    )


class ManifestBuilder:
    MANIFEST_PATH = "tie/tcv/manifest.json"
    TEMPLATE_PREFIX = "tie/"
    SKIP_TAG = "[skip-manifest]"
    BUILDER_TIMEOUT = 120  # seconds

    def __init__(self):
        self._repo_path = self.repo_path  # cache
        self.log_path = self._repo_path / ".git" / "manifest-hook.log"

    @property
    def repo_path(self) -> Path:
        out = run(["git", "rev-parse", "--show-toplevel"], capture_output=True).stdout.strip()
        return Path(out)

    def log(self, msg: str) -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(msg + "\n")
        except Exception:
            pass
        print(msg, flush=True)

    # ---------- guards ----------
    def last_commit_message(self) -> str:
        return run(
            ["git", "log", "-1", "--pretty=%B"], cwd=self._repo_path, capture_output=True
        ).stdout

    def template_files_touched(self) -> bool:
        self.log("[manifest] checking for template file changes in last commit")
        out = run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            cwd=self._repo_path,
            capture_output=True,
        ).stdout
        return any(p.strip().startswith(self.TEMPLATE_PREFIX) for p in out.splitlines())

    def should_process(self) -> bool:
        if self.SKIP_TAG in self.last_commit_message():
            self.log("[manifest] skipping due to skip tag in commit message")
            return False
        touched = self.template_files_touched()
        self.log(f"[manifest] template files touched: {touched}")
        return touched

    # ---------- hooksPath toggle (no env spam) ----------
    def _get_hooks_path(self) -> str | None:
        cp = run(
            ["git", "config", "--local", "--get", "core.hooksPath"],
            cwd=self._repo_path,
            capture_output=True,
            check=False,
        )
        val = (cp.stdout or "").strip()
        return val or None

    def _set_hooks_path(self, value: str) -> None:
        run(["git", "config", "--local", "core.hooksPath", value], cwd=self._repo_path)

    def _unset_hooks_path(self) -> None:
        run(
            ["git", "config", "--local", "--unset", "core.hooksPath"],
            cwd=self._repo_path,
            check=False,
        )

    # ---------- main steps ----------
    def build(self) -> None:
        prev_hooks = self._get_hooks_path()
        try:
            # Disable ALL hooks inside the builder by setting repo config temporarily
            self._set_hooks_path("/dev/null")

            # Also set a SINGLE env var so any nested post-commit run exits immediately
            env = os.environ.copy()
            env["MANIFEST_HOOK_DISABLED"] = "1"

            self.log(f"[manifest] building updated manifest, cwd={self._repo_path / 'tie'}")
            run(
                [sys.executable, "-u", "build_manifest.py", "tcv"],
                cwd=self._repo_path / "tie",
                timeout=self.BUILDER_TIMEOUT,
            )
        finally:
            # Restore prior hooksPath setting
            if prev_hooks is None:
                self._unset_hooks_path()
            else:
                self._set_hooks_path(prev_hooks)

    def add_manifest(self) -> None:
        self.log("[manifest] staging updated manifest")
        run(["git", "add", "--", self.MANIFEST_PATH], cwd=self._repo_path)

    def manifest_changed(self) -> bool:
        cp = run(
            ["git", "diff", "--cached", "--quiet", "--", self.MANIFEST_PATH],
            cwd=self._repo_path,
            check=False,
        )
        return cp.returncode == 1  # 1 = diff exists

    def commit(self) -> None:
        self.log("[manifest] committing updated manifest (hooks disabled for this commit)")
        run(
            [
                "git",
                "-c",
                "core.hooksPath=/dev/null",  # disable hooks for this one commit only
                "commit",
                "-m",
                f"chore: update manifest {self.SKIP_TAG}",
                "--quiet",
                "--",
                self.MANIFEST_PATH,
            ],
            cwd=self._repo_path,
        )


if __name__ == "__main__":
    # Single re-entrancy env var (your only env use)
    if os.environ.get("MANIFEST_HOOK_DISABLED") == "1":
        sys.exit(0)

    mb = ManifestBuilder()
    try:
        if not mb.should_process():
            sys.exit(0)
        mb.build()
        mb.add_manifest()
        if not mb.manifest_changed():
            mb.log("[manifest] no changes to manifest; nothing to commit")
            sys.exit(0)
        mb.commit()
        mb.log("[manifest] done")
        sys.exit(0)
    except subprocess.TimeoutExpired:
        print("[manifest] ERROR: builder timed out", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"[manifest] ERROR: {e}", file=sys.stderr)
        sys.exit(e.returncode or 1)
    except Exception as e:
        print(f"[manifest] ERROR: {e}", file=sys.stderr)
        sys.exit(1)
