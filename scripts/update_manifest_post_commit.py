#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# --- CONFIG (edit these) ---
TEMPLATE_DIR = 'tie'
MANIFEST_PATH = "tie/tcv/manifest.json"  # where your manifest is written
REPO_ROOT = Path(__file__).resolve().parents[1]  # adjust if script lives elsewhere
SCRIPT = REPO_ROOT / "tie" / "build_manifest.py"
BUILD_ARGS = [sys.executable, str(SCRIPT), "tcv"]
SKIP_TAG = "[skip-manifest]"  # prevents infinite loop


def run(
    cmd: list[str], check: bool = True, capture_output: bool = False, cwd: str | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=capture_output, text=True, cwd=cwd)


def last_commit_message() -> str:
    cp = run(["git", "log", "-1", "--pretty=%B"], capture_output=True)
    return cp.stdout or ""


def last_commit_touched_template() -> bool:
    # Files changed in HEAD (name-only)
    cp = run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"], capture_output=True
    )
    changed = [p.strip() for p in cp.stdout.splitlines() if p.strip()]
    prefix = f"{TEMPLATE_DIR.rstrip('/')}/"
    return any(p.startswith(prefix) for p in changed)


def staged_manifest_changed() -> bool:
    # Return True if manifest differs in index (staged) vs HEAD
    # We rely on exit code: 0 means no diff, 1 means diff.
    cp = subprocess.run(["git", "diff", "--cached", "--quiet", "--", MANIFEST_PATH])
    return cp.returncode == 1


def main() -> int:
    # Avoid looping on the auto-commit we make.
    if SKIP_TAG in last_commit_message():
        return 0

    # Only run if last commit touched the template dir.
    if not last_commit_touched_template():
        return 0

    print("[manifest] Template changes detected; rebuilding…")
    # Run the builder with the pre-commit Python (sys.executable)
    run(BUILD_ARGS)

    # Stage the manifest
    run(["git", "add", "--", MANIFEST_PATH])

    # Only create a commit if manifest actually changed
    if not staged_manifest_changed():
        print("[manifest] No changes to manifest; nothing to commit.")
        return 0

    # Make a separate commit and prevent re-trigger via SKIP_TAG
    run(["git", "commit", "-m", f"chore: update manifest {SKIP_TAG}", "--no-verify"])
    print("[manifest] Manifest updated and committed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as e:
        # Print useful stderr for debugging in the hook output
        sys.stderr.write(e.stderr or "")
        sys.exit(e.returncode or 1)
