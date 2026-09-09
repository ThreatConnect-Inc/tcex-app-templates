"""Fixture loading utilities — shared by all mock SDK implementations.

Fixture files are JSON files at tests/fixtures/<scope>/<name>.json.
The harness resolves which directories to load based on a three-level convention:

    tests/fixtures/common/              # loaded for every test
    tests/fixtures/{ClassName}/common/  # loaded for all tests in a class
    tests/fixtures/{ClassName}/{test}/  # loaded only for a specific test

MockSDKMixin handles the merge. Use MockSDKMixin.load_fixture for raw access in tests.

Usage in a MockSDK:
    class MockSDK(MockSDKMixin, RealSDK):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # _load_fixtures() is called automatically by the harness after construction

        def get_events(self, start, end):
            return self._data.get('events', [])

Usage in a test directly:
    records = MockSDKMixin.load_fixture(Path('tests/fixtures/common'), 'events')
"""

# standard library
import json
from pathlib import Path
from collections.abc import Generator
from typing import TypeVar

T = TypeVar('T')


class MockSDKMixin:
    """Mixin that adds fixture loading to a MockSDK class.

    Loads JSON fixture files from a list of directories in order. For the same
    filename stem, later directories win (override earlier ones entirely).

    The harness calls _load_fixtures(self.fixture_paths) automatically after
    create_mock_sdk() returns. MockSDK.__init__ does not need to accept or call it.

        class MockSDK(MockSDKMixin, RealSDK):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

            def get_events(self, start, end):
                return self._data.get('events', [])
    """

    @staticmethod
    def load_fixture(fixture_dir: Path, name: str) -> list[dict]:
        """Load a single JSON fixture file by directory and name stem.

        Returns an empty list if the file does not exist.
        """
        path = fixture_dir / f'{name}.json'
        if not path.exists():
            return []
        with path.open(encoding='utf-8') as fh:
            return json.load(fh)

    @staticmethod
    def yield_fixture_as(fixture_dir: Path, name: str, model_cls: type[T]) -> Generator[T, None, None]:
        """Load a fixture and yield each record as model_cls instances."""
        for record in MockSDKMixin.load_fixture(fixture_dir, name):
            yield model_cls(**record)

    def _load_fixtures(self, fixture_paths: list[Path]) -> None:
        """Merge fixture files from a list of directories into self._data.

        Files are loaded in order. Same filename stem in a later directory
        replaces the earlier one entirely — no partial merging.
        """
        self._data: dict = {}
        for path in fixture_paths:
            for file in sorted(path.glob('*.json')):
                self._data[file.stem] = json.loads(file.read_text(encoding='utf-8'))
