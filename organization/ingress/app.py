"""ThreatConnect Job App"""
# third-party
from tcex import TcEx
from tcex.exit import ExitCode

# first-party
from job_app import JobApp  # Import default Job App Class (Required)


class App(JobApp):
    """Job App"""

    def __init__(self, _tcex: TcEx):
        """Initialize class properties."""
        super().__init__(_tcex)

        # properties
        self.batch = self.tcex.api.tc.v2.batch(self.in_.tc_owner)

    def setup(self):
        """Perform prep/setup logic."""
        # setting the base url allow for subsequent API call
        # to be made by only providing the API endpoint/path.
        self.tcex.session.external.base_url = 'https://feodotracker.abuse.ch'

    def run(self):
        """Run main App logic."""

        with self.tcex.session.external as s:
            # https://feodotracker.abuse.ch/downloads/ipblocklist_recommended.json
            r = s.get('/downloads/ipblocklist_recommended.json')

            if r.ok:
                ti_data = r.json()

                # Example JSON
                # {
                #   "ip_address": "178.128.23.9",
                #   "port": 4125,
                #   "status": "online",
                #   "hostname": null,
                #   "as_number": 14061,
                #   "as_name": "DIGITALOCEAN-ASN",
                #   "country": "SG",
                #   "first_seen": "2021-05-16 19:49:33",
                #   "last_online": "2023-04-29",
                #   "malware": "Dridex"
                # }

                for ti in ti_data:
                    # create batch entry
                    ip_address = ti['ip_address']
                    address = self.batch.address(ip_address, rating='4.0', confidence='100')

                    # map first seen to "First Seen" attribute
                    first_seen = ti.get('first_seen')
                    if first_seen:
                        first_seen = self.tcex.util.any_to_datetime(first_seen).strftime(
                            '%Y-%m-%dT%H:%M:%SZ'
                        )
                        address.attribute('First Seen', first_seen)

                    # map last online to "Last Seen" attribute
                    last_online = ti.get('last_online')
                    if last_online:
                        last_online = self.tcex.util.any_to_datetime(last_online).strftime(
                            '%Y-%m-%dT%H:%M:%SZ'
                        )
                        address.attribute('Last Seen', last_online)

                    # map port to "Port" attribute
                    port = ti.get('port')
                    if port:
                        address.attribute('Port', port)

                    # map malware to "Malware" tag
                    malware = ti.get('malware')
                    if malware:
                        address.tag(malware)

                    # optionally save object to disk to save on memory usage
                    self.batch.save(address)
            else:
                self.tcex.exit.exit(ExitCode.SUCCESS, 'Failed to download CSV data.')

        # submit batch job
        batch_status = self.batch.submit_all()
        self.log.info(f'batch-status={batch_status}')

        self.exit_message = 'Downloaded data and create batch job.'
