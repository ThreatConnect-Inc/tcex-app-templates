#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TEMPLATE_DIR = "tie"
MANIFEST_PATH = "tie/tcv/manifest.json"
SKIP_TAG = "[skip-manifest]"


def run(cmd, *, check=True, capture_output=False, cwd=None, env=None, timeout=None):
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture_output,
        text=True,
        cwd=str(cwd) if cwd else None,
        env=env,
        timeout=timeout,
    )


def repo_root() -> Path:
    out = run(["git", "rev-parse", "--show-toplevel"], capture_output=True).stdout.strip()
    return Path(out)


REPO_ROOT = repo_root()
BUILD_CWD = REPO_ROOT / "tie"
SCRIPT = BUILD_CWD / "build_manifest.py"
BUILD_ARGS = [sys.executable, "-u", str(SCRIPT), "tcv"]


def last_commit_message() -> str:
    return run(["git", "log", "-1", "--pretty=%B"], capture_output=True, cwd=REPO_ROOT).stdout or ""


def last_commit_touched_template() -> bool:
    out = run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        capture_output=True,
        cwd=REPO_ROOT,
    ).stdout
    prefix = f"{TEMPLATE_DIR.rstrip('/')}/"
    return any(p.strip().startswith(prefix) for p in out.splitlines())


def staged_manifest_changed() -> bool:
    cp = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", MANIFEST_PATH], cwd=str(REPO_ROOT)
    )
    return cp.returncode == 1


def main() -> int:
    # print for visibility
    print("[manifest] post-commit hook running…")

    if SKIP_TAG in last_commit_message():
        return 0
    if not last_commit_touched_template():
        print("[manifest] No template changes in last commit; exiting.")
        return 0

    print("[manifest] Template changes detected; rebuilding…")
    # Safety timeout so we never hang forever:
    run(BUILD_ARGS, cwd=BUILD_CWD, timeout=60)

    run(["git", "add", "--", MANIFEST_PATH], cwd=REPO_ROOT, timeout=10)

    if not staged_manifest_changed():
        print("[manifest] No changes to manifest; nothing to commit.")
        return 0

    # Skip our own hook on the auto-commit AND disable GPG signing
    env = os.environ.copy()
    env["SKIP"] = (
        "update-manifest-after-template-change"  # <-- your hook id in .pre-commit-config.yaml
    )

    run(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",  # <— no hooks for this commit
            "-c",
            "commit.gpgsign=false",  # <— avoid GPG prompt
            "commit",
            "-m",
            f"chore: update manifest {SKIP_TAG}",
            "--quiet",
            "--no-verify",  # skips pre-commit/commit-msg if hooks were enabled
        ],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        timeout=60,
    )
    print("[manifest] Manifest updated and committed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.TimeoutExpired:
        print("[manifest] ERROR: builder timed out.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        sys.stderr.write(e.stderr or "")
        sys.exit(e.returncode or 1)
