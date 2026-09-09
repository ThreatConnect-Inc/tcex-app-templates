"""Pytest configuration for this TIE app's tests.

Puts the app's own modules and its vendored dependencies on sys.path before any
test imports, mirroring the production runtime environment.

Resulting sys.path priority (highest first):
  1. app root     — app modules (model, task, sdk, core, app_inputs, ...)
  2. deps/        — production packages (pydantic v1, tcex, ...)
  3. deps_tests/  — test-only packages (pytest, fakeredis, ...)
  4. tests/       — so `import tcex_testing` resolves to tests/tcex_testing/

deps/ must outrank deps_tests/ so tests resolve the same package versions the
app runs against in production — most importantly pydantic v1, which a test-only
dependency could otherwise shadow with v2.

This file is intentionally sys.path setup only. Shared per-test state belongs on
the AppTestCase harness in tests/harness/base.py, not in fixtures here.
"""

import sys
from pathlib import Path

APP_DIR = Path(__file__).parent.parent
TESTS_DIR = APP_DIR / 'tests'
DEPS_DIR = APP_DIR / 'deps'
DEPS_TESTS_DIR = APP_DIR / 'deps_tests'

# Listed highest-priority first; inserted in reverse so index 0 ends up as APP_DIR.
_PATH_PRIORITY = (APP_DIR, DEPS_DIR, DEPS_TESTS_DIR, TESTS_DIR)

for _path in reversed(_PATH_PRIORITY):
    _entry = str(_path)
    if _entry not in sys.path:
        sys.path.insert(0, _entry)
