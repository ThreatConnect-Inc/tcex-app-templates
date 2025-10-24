#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TEMPLATE_DIR = "tie"
MANIFEST_PATH = "tie/tcv/manifest.json"
SKIP_TAG = "[skip-manifest]"
BUILDER_TIMEOUT = 120


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


def repo_root() -> Path:
    out = run(["git", "rev-parse", "--show-toplevel"], capture_output=True).stdout.strip()
    return Path(out)


REPO_ROOT = repo_root()
BUILD_CWD = REPO_ROOT / TEMPLATE_DIR
SCRIPT = BUILD_CWD / "build_manifest.py"
BUILD_ARGS = [sys.executable, "-u", str(SCRIPT), "tcv"]


def last_commit_message() -> str:
    return run(["git", "log", "-1", "--pretty=%B"], capture_output=True, cwd=REPO_ROOT).stdout


def last_commit_touched_template() -> bool:
    out = run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        capture_output=True,
        cwd=REPO_ROOT,
    ).stdout
    prefix = f"{TEMPLATE_DIR.rstrip('/')}/"
    return any(p.strip().startswith(prefix) for p in out.splitlines())


def staged_manifest_changed() -> bool:
    cp = run(
        ["git", "diff", "--cached", "--quiet", "--", MANIFEST_PATH], cwd=REPO_ROOT, check=False
    )
    return cp.returncode == 1


def main():
    print("[manifest] post-commit hook start")

    if SKIP_TAG in last_commit_message():
        print("[manifest] skip tag detected; exiting")
        return 0

    if not last_commit_touched_template():
        print("[manifest] no template changes; exiting")
        return 0

    print("[manifest] template changes detected; rebuilding…")
    run(BUILD_ARGS, cwd=BUILD_CWD, timeout=BUILDER_TIMEOUT)

    run(["git", "add", "--", MANIFEST_PATH], cwd=REPO_ROOT)

    if not staged_manifest_changed():
        print("[manifest] no changes to manifest; nothing to commit")
        return 0

    # ✅ Commit once, skipping all hooks
    run(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",  # disables *all* hooks
            "commit",
            "-m",
            f"chore: update manifest {SKIP_TAG}",
        ],
        cwd=REPO_ROOT,
    )

    print("[manifest] manifest updated and committed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.TimeoutExpired:
        print("[manifest] ERROR: builder timed out", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"[manifest] ERROR: subprocess failed: {e}", file=sys.stderr)
        sys.exit(1)
