#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# --- CONFIG ---
TEMPLATE_DIR = "tie"  # watched dir (repo-relative)
MANIFEST_PATH = "tie/tcv/manifest.json"  # repo-relative
SKIP_TAG = "[skip-manifest]"  # prevents loop


# Resolve repo root robustly (works from pre-commit env too)
def repo_root() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], check=True, capture_output=True, text=True
        ).stdout.strip()
        return Path(out)
    except Exception:
        # Fallback: scripts/ is one level under repo root
        return Path(__file__).resolve().parents[1]


REPO_ROOT = repo_root()
BUILD_CWD = REPO_ROOT / "tie"  # <-- run builder *inside* tie/
SCRIPT = BUILD_CWD / "build_manifest.py"  # absolute path to the script
BUILD_ARGS = [sys.executable, "-u", str(SCRIPT), "tcv"]  # -u = unbuffered


def run(cmd: list[str], *, check=True, capture_output=False, cwd: Path | None = None):
    return subprocess.run(
        cmd, check=check, capture_output=capture_output, text=True, cwd=str(cwd) if cwd else None
    )


def last_commit_message() -> str:
    cp = run(["git", "log", "-1", "--pretty=%B"], capture_output=True, cwd=REPO_ROOT)
    return cp.stdout or ""


def last_commit_touched_template() -> bool:
    cp = run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        capture_output=True,
        cwd=REPO_ROOT,
    )
    changed = [p.strip() for p in cp.stdout.splitlines() if p.strip()]
    prefix = f"{TEMPLATE_DIR.rstrip('/')}/"
    return any(p.startswith(prefix) for p in changed)


def staged_manifest_changed() -> bool:
    # 0 = no diff, 1 = diff
    cp = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", MANIFEST_PATH], cwd=str(REPO_ROOT)
    )
    return cp.returncode == 1


def main() -> int:
    # Optional: prove the hook is running
    print(f"[manifest] post-commit hook running (repo_root={REPO_ROOT}, build_cwd={BUILD_CWD})")

    if SKIP_TAG in last_commit_message():
        return 0
    if not last_commit_touched_template():
        print("[manifest] No template changes in last commit; exiting.")
        return 0

    print("[manifest] Template changes detected; rebuilding…")
    # Run builder *inside* tie/
    run(BUILD_ARGS, cwd=BUILD_CWD)

    # Stage manifest from repo root
    run(["git", "add", "--", MANIFEST_PATH], cwd=REPO_ROOT)

    if not staged_manifest_changed():
        print("[manifest] No changes to manifest; nothing to commit.")
        return 0

    # Make separate commit; prevent loop via SKIP_TAG
    run(["git", "commit", "-m", f"chore: update manifest {SKIP_TAG}", "--no-verify"], cwd=REPO_ROOT)
    print("[manifest] Manifest updated and committed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as e:
        # surface stderr for easier debugging in pre-commit output
        sys.stderr.write(e.stderr or "")
        sys.exit(e.returncode or 1)
