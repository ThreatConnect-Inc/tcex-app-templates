"""Class for /api/1.0/job/request endpoint"""

import tarfile
from functools import cached_property
from io import BytesIO
from pathlib import Path

from spectree import Response

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_util
from core.api.validation.models.query_param_model import QueryParamModel
from core.dao.job_dao import JobRequestDAO


class DownloadFilesResource(EndpointBase):
    """Class for /api/db/download endpoint"""

    def __init__(self, download_path: Path):
        """Initialize the class."""
        self.download_path = download_path

    @cached_property
    def dao(self) -> JobRequestDAO:
        """Return the dao."""
        return JobRequestDAO(self.db, self.settings)

    @spec.validate(
        resp=Response('HTTP_200'),
        query=QueryParamModel,
        skip_validation=True,
        tags=[tag_util],
    )
    def on_get(
        self,
        req: FalconRequest,  # noqa: ARG002
        resp: FalconResponse,
        query_params: QueryParamModel,  # noqa: ARG002
    ):
        """Download database file."""
        inmemory_file = BytesIO()
        with tarfile.open('', 'w:bz2', fileobj=inmemory_file) as tar:
            for path in self.download_path.rglob('*'):
                tar.add(
                    path,
                    arcname=self.download_path.name / path.relative_to(self.download_path),
                )
        size = inmemory_file.tell()
        inmemory_file.seek(0)

        resp.downloadable_as = f'{self.download_path.name}.tar.bz2'
        resp.content_type = 'application/tar+bz2'
        resp.set_stream(inmemory_file, size)
