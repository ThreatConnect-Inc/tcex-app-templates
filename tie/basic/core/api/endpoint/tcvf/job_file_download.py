"""Class for /api/tc/app-config endpoint"""

from pathlib import Path

import falcon
from spectree import Response

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_job
from core.api.validation.models import QueryParamModel


class QueryParams(QueryParamModel):
    """Query parameters for the /api/tc/job-file-download endpoint"""

    file_name: str


class JobFileDownload(EndpointBase):
    """Class for /api/tc/app-config endpoint"""

    @spec.validate(
        resp=Response('HTTP_200'),
        query=QueryParams,
        skip_validation=True,
        tags=[tag_job],
    )
    def on_get(
        self,
        _req: FalconRequest,
        resp: FalconResponse,
        query_params: QueryParams,
        job_id: str,
    ):
        """Download a job files."""
        file_path = None

        if query_params.file_name.endswith('.jsondb') or query_params.file_name.endswith(
            '.jsondb.gz'
        ):
            file_path = next(self.settings.base_path.rglob(f'*{job_id}.jsondb*'), None)
        else:
            path_parts = query_params.file_name.split('/')
            job_dir = next(
                (p for p in self.settings.base_path.rglob(f'*{job_id}') if p.is_dir()), None
            )
            if job_dir is None:
                raise falcon.HTTPNotFound

            combined_path = job_dir.joinpath(*path_parts)

            if job_dir in combined_path.parents:
                file_path = combined_path

        if not file_path:
            raise falcon.HTTPNotFound

        match file_path.name.split('.')[-1]:
            case 'json':
                resp.content_type = 'application/json'
            case 'jsondb':
                resp.content_type = 'application/json'
            case 'txt':
                resp.content_type = 'text/plain'
            case 'gz':
                resp.content_type = 'application/gzip'

        resp.downloadable_as = file_path.name
        resp.set_stream(Path.open(file_path, 'rb'), file_path.stat().st_size)
