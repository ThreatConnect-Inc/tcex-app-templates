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
SKIP_TAG = "[skip-manifest]"  # guard tag in commit message
BUILDER_TIMEOUT = 180  # seconds for builder before we kill it


# --- helpers ------------------------------------------------------------------
def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], check=True, capture_output=True, text=True
    ).stdout.strip()
    return Path(out)


REPO_ROOT = repo_root()
BUILD_CWD = REPO_ROOT / "tie"
SCRIPT = BUILD_CWD / "build_manifest.py"
BUILD_ARGS = [sys.executable, "-u", str(SCRIPT), "tcv"]
LOG_FILE = REPO_ROOT / ".git" / "manifest-hook.log"


def log_line(msg: str) -> None:
    # append to file + print to stdout
    try:
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except Exception:
        pass
    print(msg, flush=True)


def last_commit_message() -> str:
    return (
        subprocess.run(
            ["git", "log", "-1", "--pretty=%B"],
            check=True,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=10,
        ).stdout
        or ""
    )


def last_commit_touched_template() -> bool:
    out = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=10,
    ).stdout
    prefix = f"{TEMPLATE_DIR.rstrip('/')}/"
    return any(p.strip().startswith(prefix) for p in out.splitlines())


def staged_manifest_changed() -> bool:
    # 0 = no diff, 1 = diff
    cp = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", MANIFEST_PATH], cwd=str(REPO_ROOT), timeout=10
    )
    return cp.returncode == 1


def stream_run_builder(cmd: list[str], cwd: Path, timeout_s: int, base_env: dict) -> int:
    """Run builder, stream output to log, and enforce timeout. Returns exit code."""
    env = base_env.copy()
    # force non-interactive, unbuffered, no pagers
    env.setdefault("CI", "1")
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GIT_PAGER", "cat")
    env.setdefault("PAGER", "cat")

    log_line(f"[manifest] builder start: cwd={cwd} cmd={' '.join(cmd)}")

    # Start process in its own process group so we can kill the whole tree on timeout
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,  # create new process group
    )

    start = time.time()
    last_lines: list[str] = []

    try:
        assert proc.stdout is not None
        # stream lines until done or timeout
        while True:
            # read line with small timeout-ish polling
            if proc.poll() is not None:
                # process ended; drain remaining output
                for line in proc.stdout.read().splitlines():
                    log_line(f"[builder] {line}")
                    last_lines.append(line)
                    if len(last_lines) > 20:
                        last_lines.pop(0)
                break

            line = proc.stdout.readline()
            if line:
                line = line.rstrip("\n")
                log_line(f"[builder] {line}")
                last_lines.append(line)
                if len(last_lines) > 20:
                    last_lines.pop(0)

            if time.time() - start > timeout_s:
                raise TimeoutError("builder timeout")

            # tiny sleep to avoid busy loop when no output
            time.sleep(0.02)

    except TimeoutError:
        # kill whole process group
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            proc.kill()
        log_line("[manifest] ERROR: builder timed out; killing process tree")
        if last_lines:
            log_line("[manifest] tail of builder output before timeout:")
            for ln in last_lines[-10:]:
                log_line(f"[tail] {ln}")
        return 124  # conventional timeout code
    finally:
        try:
            proc.wait(timeout=5)
        except Exception:
            pass

    rc = proc.returncode or 0
    log_line(f"[manifest] builder exit code: {rc}")
    return rc


def main() -> int:
    log_line("[manifest] post-commit hook start")

    msg = last_commit_message()
    if SKIP_TAG in msg:
        log_line("[manifest] skip tag detected; exiting")
        return 0

    if not last_commit_touched_template():
        log_line("[manifest] last commit did not touch template dir; exiting")
        return 0

    log_line("[manifest] template changes detected; rebuilding…")

    base_env = os.environ.copy()

    rc = stream_run_builder(BUILD_ARGS, cwd=BUILD_CWD, timeout_s=BUILDER_TIMEOUT, base_env=base_env)
    if rc != 0:
        log_line(f"[manifest] ERROR: builder failed with code {rc}")
        return rc

    subprocess.run(
        ["git", "add", "--", MANIFEST_PATH], check=True, cwd=REPO_ROOT, env=base_env, timeout=10
    )

    if not staged_manifest_changed():
        log_line("[manifest] no changes to manifest; nothing to commit")
        return 0

    # commit manifest update with ALL hooks disabled + no signing (avoid recursion/prompts)
    subprocess.run(
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
        check=True,
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
