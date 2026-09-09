"""Job app result — returned by JobTestCase.run().

Chain assertions off it:

    result = self.run(Profile(inputs={'hours_back': 24}))
    result.assert_no_batch_errors()

    indicators = result.fetch_batch_records('indicator')
    assert len(indicators) >= 1
"""

# standard library
import gzip
import json
from pathlib import Path


class JobResult:
    """Returned by JobTestCase.run() — chain assertions off it."""

    def __init__(self, exit_code: int, exit_message: str | None, tcex, output_dir: Path) -> None:
        self.exit_code = exit_code
        self.exit_message = exit_message
        self.tcex = tcex
        self._output_dir = output_dir

    # TODO: batch file helpers — not all job apps write batch files to disk;
    # some stream directly to the TC batch API. Uncomment and adapt if needed
    # for apps that do write batch output files.
    #
    # def assert_no_batch_errors(self) -> 'JobResult':
    #     error_files = list(self._output_dir.rglob('*batch-errors*'))
    #     assert not error_files, (
    #         f'Expected no batch errors, found {len(error_files)}: '
    #         f'{[f.name for f in error_files]}'
    #     )
    #     return self
    #
    # def fetch_batch_records(self, key: str) -> list[dict]:
    #     """Return all records for key ('indicator', 'group', etc.) from batch .json.gz files."""
    #     records: list[dict] = []
    #     for path in self._output_dir.rglob('*batch*.json.gz'):
    #         with gzip.open(path, 'rt', encoding='utf-8') as fh:
    #             data = json.load(fh)
    #         records.extend(data.get(key, []))
    #     return records
