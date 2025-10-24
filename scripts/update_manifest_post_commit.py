#!/usr/bin/env python3
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# --- CONFIG ---
TEMPLATE_DIR = "tie"  # watched dir (repo-relative)
MANIFEST_PATH = "tie/tcv/manifest.json"  # repo-relative
SKIP_TAG = "[skip-manifest]"  # guard tag
BUILDER_TIMEOUT = 180  # seconds


# --- simple runner ------------------------------------------------------------
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

# --- logging ------------------------------------------------------------------
LOG_FILE = REPO_ROOT / ".git" / "manifest-hook.log"


def log_line(msg: str) -> None:
    try:
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except Exception:
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
        ["git", "diff", "--cached", "--quiet", "--", MANIFEST_PATH], cwd=str(REPO_ROOT), timeout=10
    )
    return cp.returncode == 1  # 1 = diff, 0 = no diff


# --- stream the builder and enforce timeout -----------------------------------
def stream_run_builder(cmd: list[str], cwd: Path, timeout_s: int, base_env: dict) -> int:
    env = base_env.copy()
    # Force non-interactive behavior and unbuffered output
    env.setdefault("CI", "1")
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GIT_PAGER", "cat")
    env.setdefault("PAGER", "cat")
    # CRITICAL: disable THIS hook if the builder triggers commits
    env["MANIFEST_HOOK_DISABLED"] = "1"

    log_line(f"[manifest] builder start: cwd={cwd} cmd={' '.join(cmd)}")

    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,  # separate process group
    )

    start = time.time()
    tail: list[str] = []
    try:
        assert proc.stdout is not None
        while True:
            if proc.poll() is not None:
                for line in proc.stdout.read().splitlines():
                    log_line(f"[builder] {line}")
                    tail.append(line)
                    if len(tail) > 50:
                        tail.pop(0)
                break

            line = proc.stdout.readline()
            if line:
                line = line.rstrip("\n")
                log_line(f"[builder] {line}")
                tail.append(line)
                if len(tail) > 50:
                    tail.pop(0)

            if time.time() - start > timeout_s:
                raise TimeoutError("builder timeout")

            time.sleep(0.02)
    except TimeoutError:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            proc.kill()
        log_line("[manifest] ERROR: builder timed out; killing process tree")
        if tail:
            log_line("[manifest] tail before timeout:")
            for ln in tail[-15:]:
                log_line(f"[tail] {ln}")
        return 124
    finally:
        try:
            proc.wait(timeout=5)
        except Exception:
            pass

    rc = proc.returncode or 0
    log_line(f"[manifest] builder exit code: {rc}")
    return rc


def main() -> int:
    # EARLY EXIT: if builder asked us to be disabled, do nothing
    if os.environ.get("MANIFEST_HOOK_DISABLED") == "1":
        return 0

    log_line("[manifest] post-commit hook start")

    # Self-recursion guard: ensure SCRIPT is not this file
    if Path(__file__).resolve() == SCRIPT.resolve():
        log_line(
            "[manifest] ERROR: build_manifest.py resolves to THIS hook script. Fix SCRIPT path."
        )
        return 1

    if SKIP_TAG in last_commit_message():
        log_line("[manifest] skip tag detected; exiting")
        return 0
    if not last_commit_touched_template():
        log_line("[manifest] last commit did not touch template dir; exiting")
        return 0

    log_line("[manifest] template changes detected; rebuilding…")

    base_env = os.environ.copy()

    # Run the real builder
    rc = stream_run_builder(BUILD_ARGS, cwd=BUILD_CWD, timeout_s=BUILDER_TIMEOUT, base_env=base_env)
    if rc != 0:
        log_line(f"[manifest] ERROR: builder failed with code {rc}")
        return rc

    # Stage and commit manifest update
    run(["git", "add", "--", MANIFEST_PATH], cwd=REPO_ROOT, env=base_env, timeout=10)

    if not staged_manifest_changed():
        log_line("[manifest] no changes to manifest; nothing to commit")
        return 0

    # commit without any hooks or signing (no recursion, no prompts)
    run(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            f"chore: update manifest {SKIP_TAG}",
            "--quiet",
            "--no-verify",
        ],
        cwd=REPO_ROOT,
        env=base_env,
        timeout=30,
    )
    log_line("[manifest] manifest updated and committed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as e:
        if e.stderr:
            log_line(e.stderr.rstrip())
        else:
            log_line(f"[manifest] ERROR: subprocess failed (code={e.returncode})")
        sys.exit(e.returncode or 1)
    except Exception as e:
        log_line(f"[manifest] ERROR: {e}")
        sys.exit(1)
