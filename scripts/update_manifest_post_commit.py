#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# --- CONFIG ---
TEMPLATE_DIR = "tie"  # watched dir (repo-relative)
MANIFEST_PATH = "tie/tcv/manifest.json"  # repo-relative
SKIP_TAG = "[skip-manifest]"  # guard tag in commit message


# --- subprocess helper --------------------------------------------------------
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


# --- paths --------------------------------------------------------------------
def repo_root() -> Path:
    out = run(["git", "rev-parse", "--show-toplevel"], capture_output=True).stdout.strip()
    return Path(out)


REPO_ROOT = repo_root()
BUILD_CWD = REPO_ROOT / "tie"
SCRIPT = BUILD_CWD / "build_manifest.py"
BUILD_ARGS = [sys.executable, "-u", str(SCRIPT), "tcv"]

# --- logging (file + stdout) --------------------------------------------------
LOG_FILE = REPO_ROOT / ".git" / "manifest-hook.log"


def log_line(msg: str) -> None:
    try:
        LOG_FILE.write_text((LOG_FILE.read_text() if LOG_FILE.exists() else "") + msg + "\n")
    except Exception:
        # Logging must never crash the hook.
        pass
    print(msg, flush=True)


# --- git helpers --------------------------------------------------------------
def last_commit_message() -> str:
    return (
        run(
            ["git", "log", "-1", "--pretty=%B"], capture_output=True, cwd=REPO_ROOT, timeout=10
        ).stdout
        or ""
    )


def last_commit_touched_template() -> bool:
    out = run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        capture_output=True,
        cwd=REPO_ROOT,
        timeout=10,
    ).stdout
    prefix = f"{TEMPLATE_DIR.rstrip('/')}/"
    return any(p.strip().startswith(prefix) for p in out.splitlines())


def staged_manifest_changed() -> bool:
    cp = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", MANIFEST_PATH],
        cwd=str(REPO_ROOT),
        timeout=10,
    )
    # 0 = no diff, 1 = diff
    return cp.returncode == 1


def main() -> int:
    log_line("[manifest] post-commit hook start")

    # Fast exits
    if SKIP_TAG in last_commit_message():
        log_line("[manifest] skip tag detected; exiting")
        return 0
    if not last_commit_touched_template():
        log_line("[manifest] last commit did not touch template dir; exiting")
        return 0

    log_line("[manifest] template changes detected; rebuilding…")

    # Ensure git never tries to page output (can hang in PTY contexts)
    base_env = os.environ.copy()
    base_env.setdefault("GIT_PAGER", "cat")
    base_env.setdefault("PAGER", "cat")
    base_env.setdefault("GIT_TERMINAL_PROMPT", "0")  # avoid interactive prompts

    # Run builder *inside* tie/
    run(BUILD_ARGS, cwd=BUILD_CWD, env=base_env, timeout=120)

    # Stage manifest from repo root
    run(["git", "add", "--", MANIFEST_PATH], cwd=REPO_ROOT, env=base_env, timeout=10)

    if not staged_manifest_changed():
        log_line("[manifest] no changes to manifest; nothing to commit")
        return 0

    # Make a separate commit for the manifest update, bypassing ALL hooks and GPG signing
    # so there is zero chance of recursion or interactive prompts.
    run(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",  # no hooks for THIS commit
            "-c",
            "commit.gpgsign=false",  # avoid GPG prompt
            "commit",
            "-m",
            f"chore: update manifest {SKIP_TAG}",
            "--quiet",
            "--no-verify",  # belt-and-suspenders
        ],
        cwd=REPO_ROOT,
        env=base_env,
        timeout=60,
    )
    log_line("[manifest] manifest updated and committed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.TimeoutExpired:
        log_line("[manifest] ERROR: timeout hit")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        # Surface stderr for debugging in pre-commit output and file log
        if e.stderr:
            log_line(e.stderr.rstrip())
        else:
            log_line("[manifest] ERROR: subprocess failed (no stderr)")
        sys.exit(e.returncode or 1)
    except Exception as e:
        log_line(f"[manifest] ERROR: {e}")
        sys.exit(1)
