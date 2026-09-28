"""Class for /api/tc_info endpoint"""

import falcon

from core.api.endpoint.endpoint_base_abc import EndpointBaseABC


class TcInfoResource(EndpointBaseABC):
    """Class for /api/tc_info endpoint"""

    # pylint: disable=W0613
    def on_get(self, _req: falcon.Request, resp: falcon.Response, _task_name: str | None = None):
        """Return the list of TC owners accessible to the configured API credentials."""
        try:
            owners = sorted([o.model.name for o in self.tcex.api.tc.v3.security.owners()])
        except Exception as ex:
            self.log.warning(f'tc-info: failed to retrieve owners: {ex}')
            owners = []

        resp.media = {'owners': owners}
