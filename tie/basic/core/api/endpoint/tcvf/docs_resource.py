"""Packaged documentation API endpoint.

Every TIE app ships its user guide at the same path, so there is nothing for an app to
declare and nothing to configure — this serves `docs/user-guide.md` and that is the whole
contract. There is deliberately no way to ask for a different file: a request cannot name
a path, so a path cannot be traversed.
"""

from pathlib import Path

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse

# Module-relative so this does not depend on the process working directory.
# core/api/endpoint/tcvf/docs_resource.py -> up four is the app root.
USER_GUIDE = Path(__file__).resolve().parents[4] / 'docs' / 'user-guide.md'


class DocsResource(EndpointBase):
    """GET /api/docs"""

    def on_get(self, _req: FalconRequest, resp: FalconResponse):
        """Return the packaged user guide as `{markdown}`.

        The title is the document's own `# ` heading, so it is not served separately —
        one place to change it, and no way for the two to disagree.
        """
        try:
            markdown = USER_GUIDE.read_text(encoding='utf-8')
        except FileNotFoundError:
            self.log.exception(f'action=docs-get, status=missing, path={USER_GUIDE}')
            resp.status = '404 Not Found'
            resp.media = {'error': 'No user guide is packaged with this app.'}
            return

        resp.media = {'markdown': markdown}
