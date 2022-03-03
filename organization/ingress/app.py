"""ThreatConnect Job App"""
# standard library
import csv
from typing import TYPE_CHECKING

# third-party
from tcex.exit import ExitCode

# first-party
from job_app import JobApp  # Import default Job App Class (Required)

if TYPE_CHECKING:
    # third-party
    from tcex import TcEx
    from tcex.api.tc.v2.batch import Batch
    from tcex.api.tc.v2.batch.indicator import File
    from tcex.sessions.external_session import ExternalSession


class App(JobApp):
    """Job App"""

    def __init__(self, _tcex: 'TcEx') -> None:
        """Initialize class properties."""
        super().__init__(_tcex)

        # properties
        self.batch: 'Batch' = self.tcex.v2.batch(self.inputs.model.tc_owner)
        self.session = None

    def setup(self) -> None:
        """Perform prep/setup logic."""
        # using tcex session_external to get built-in features (e.g., proxy, logging, retries)
        self.session: 'ExternalSession' = self.tcex.session_external

        # setting the base url allow for subsequent API call to be made by only
        # providing the API endpoint/path.
        self.session.base_url = 'https://feodotracker.abuse.ch'

    def run(self) -> None:
        """Run main App logic."""

        with self.session as s:
            r = s.get('downloads/malware_hashes.csv')

            if r.ok:
                decoded_content: str = r.content.decode('utf-8').splitlines()

                reader: object = csv.reader(decoded_content, delimiter=',', quotechar='"')
                for row in reader:
                    # CSV headers
                    # Firstseen,MD5hash,Malware

                    # skip comments
                    if row[0].startswith('#'):
                        continue

                    # create batch entry
                    indicator_value: str = row[1]
                    file_hash: 'File' = self.batch.file(
                        indicator_value, rating='4.0', confidence='100'
                    )
                    file_hash.tag(row[2])

                    # add occurrence to batch entry
                    occurrence: object = file_hash.occurrence()
                    occurrence.date = row[0]
                    self.batch.save(file_hash)  # optionally save object to disk
            else:
                self.tcex.exit(ExitCode.SUCCESS, 'Failed to download CSV data.')

        # submit batch job
        batch_status: list = self.batch.submit_all()
        self.log.info(f'batch-status={batch_status}')

        self.exit_message = (  # pylint: disable=attribute-defined-outside-init
            'Downloaded data and create batch job.'
        )
