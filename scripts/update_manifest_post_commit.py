#!/usr/bin/env python3
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# --- CONFIG -------------------------------------------------------------------
TEMPLATE_DIR = "tie"  # watched dir (repo-relative)
MANIFEST_PATH = "tie/tcv/manifest.json"  # repo-relative
SKIP_TAG = "[skip-manifest]"  # guard tag
BUILDER_TIMEOUT = 180  # seconds


# --- small helpers ------------------------------------------------------------
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

LOG_FILE = REPO_ROOT / ".git" / "manifest-hook.log"
LOCK_FILE = REPO_ROOT / ".git" / "manifest-hook.lock"


def log_line(msg: str) -> None:
    try:
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except Exception:
        pass
    print(msg, flush=True)


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


# --- hook path detection / disable -------------------------------------------
def get_hooks_dir() -> Path:
    """Resolve the active hooks directory (core.hooksPath or .git/hooks)."""
    try:
        out = run(
            ["git", "config", "--get", "core.hooksPath"],
            capture_output=True,
            cwd=REPO_ROOT,
            timeout=5,
        ).stdout.strip()
    except Exception:
        out = ""
    if out:
        p = (REPO_ROOT / out).resolve()
    else:
        p = (REPO_ROOT / ".git" / "hooks").resolve()
    return p


def disable_post_commit_hook() -> Optional[Path]:
    """Temporarily rename the post-commit hook so it cannot run."""
    hooks_dir = get_hooks_dir()
    post_commit = hooks_dir / "post-commit"
    if post_commit.exists():
        backup = hooks_dir / "post-commit.disabled.by.manifest"
        try:
            post_commit.rename(backup)
            log_line(f"[manifest] temporarily disabled hook: {post_commit}")
            return backup
        except Exception as e:
            log_line(f"[manifest] WARN: failed to disable hook ({e}); continuing")
    return None


def enable_post_commit_hook(backup_path: Optional[Path]) -> None:
    if not backup_path:
        return
    try:
        orig = backup_path.with_name("post-commit")
        # If an updated hook was installed during the run, keep it; otherwise restore ours.
        if not orig.exists():
            backup_path.rename(orig)
        else:
            # If orig exists, remove our backup to avoid clutter.
            backup_path.unlink(missing_ok=True)  # py3.8+: wrap in try for older
        log_line("[manifest] restored post-commit hook")
    except Exception as e:
        log_line(f"[manifest] WARN: failed to restore hook ({e})")


# --- builder runner with streamed output + env guards -------------------------
def stream_run_builder(cmd: list[str], cwd: Path, timeout_s: int, base_env: dict) -> int:
    env = base_env.copy()
    # Non-interactive / unbuffered everywhere
    env.setdefault("CI", "1")
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GIT_PAGER", "cat")
    env.setdefault("PAGER", "cat")
    # tell any nested invocation of this script to exit immediately
    env["MANIFEST_HOOK_DISABLED"] = "1"
    # Disable ALL git hooks for every child git call from the builder, even if the
    # builder sets core.hooksPath via config files; env-based injected config is high priority.
    env["GIT_CONFIG_COUNT"] = str(int(env.get("GIT_CONFIG_COUNT", "0")) + 1)
    env[f"GIT_CONFIG_KEY_{int(env['GIT_CONFIG_COUNT']) - 1}"] = "core.hooksPath"
    env[f"GIT_CONFIG_VALUE_{int(env['GIT_CONFIG_COUNT']) - 1}"] = "/dev/null"

    log_line(f"[manifest] builder start: cwd={cwd} cmd={' '.join(cmd)}")

    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,  # separate process group so we can kill all children
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
                    if len(tail) > 80:
                        tail.pop(0)
                break

            line = proc.stdout.readline()
            if line:
                line = line.rstrip("\n")
                log_line(f"[builder] {line}")
                tail.append(line)
                if len(tail) > 80:
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
            for ln in tail[-20:]:
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


# --- main ---------------------------------------------------------------------
def main() -> int:
    # Early exits
    if os.environ.get("MANIFEST_HOOK_DISABLED") == "1":
        return 0
    if LOCK_FILE.exists():
        log_line("[manifest] lock present; skipping to avoid re-entry")
        return 0
    try:
        LOCK_FILE.write_text(str(os.getpid()))
    except Exception:
        pass

    try:
        log_line("[manifest] post-commit hook start")

        # Self-guard: SCRIPT must not be this file
        if Path(__file__).resolve() == SCRIPT.resolve():
            log_line("[manifest] ERROR: SCRIPT resolves to this hook. Fix SCRIPT path.")
            return 1

        if SKIP_TAG in last_commit_message():
            log_line("[manifest] skip tag detected; exiting")
            return 0
        if not last_commit_touched_template():
            log_line("[manifest] last commit did not touch template dir; exiting")
            return 0

        log_line("[manifest] template changes detected; rebuilding…")

        base_env = os.environ.copy()

        # **Temporarily disable the repository's post-commit hook file**
        backup = disable_post_commit_hook()
        try:
            rc = stream_run_builder(
                BUILD_ARGS, cwd=BUILD_CWD, timeout_s=BUILDER_TIMEOUT, base_env=base_env
            )
        finally:
            enable_post_commit_hook(backup)

        if rc != 0:
            log_line(f"[manifest] ERROR: builder failed with code {rc}")
            return rc

        run(["git", "add", "--", MANIFEST_PATH], cwd=REPO_ROOT, env=base_env, timeout=10)

        if not staged_manifest_changed():
            log_line("[manifest] no changes to manifest; nothing to commit")
            return 0

        # Commit manifest update with ALL hooks disabled + no signing (no recursion, no prompts)
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

    finally:
        try:
            LOCK_FILE.unlink(missing_ok=True)
        except Exception:
            pass


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
