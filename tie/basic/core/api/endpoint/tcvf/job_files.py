"""Class for /api/tc/app-config endpoint"""

from spectree import Response

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_job


class JobFiles(EndpointBase):
    """Class for /api/tc/app-config endpoint"""

    @spec.validate(
        resp=Response('HTTP_200'),
        skip_validation=True,
        tags=[tag_job],
    )
    def on_get(self, _req: FalconRequest, resp: FalconResponse, job_id: str):
        """Get a list of downloadable files."""
        paths = [p.name for p in self.settings.base_path.rglob(f'*{job_id}.jsondb*')]

        job_dir = [p for p in self.settings.base_path.rglob(f'*{job_id}') if p.is_dir()]

        if len(job_dir) == 1:
            for file in (p for p in job_dir[0].rglob('*') if p.is_file()):
                if file.name == 'request_id.txt':
                    continue  # don't need this if we already have the job id
                paths.append(f'{file.parent.name}/{file.name}')

        resp.media = sorted(paths)
