"""Class for /api/task endpoint"""

from spectree import Response

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_task
from core.api.validation.models.query_param_filter_pagination_model import (
    QueryParamFilterPaginationModel,
)
from core.model.tie.task_setting_model import TaskPaginatedResponseModel


class TaskCollection(EndpointBase):
    """Class for /api/task endpoint"""

    @spec.validate(
        query=QueryParamFilterPaginationModel,
        resp=Response(HTTP_200=TaskPaginatedResponseModel),
        skip_validation=True,
        tags=[tag_task],
    )
    def on_get(
        self,
        _req: FalconRequest,
        resp: FalconResponse,
        query_params: QueryParamFilterPaginationModel,
    ):
        """Get task data."""
        response_media = []
        for task in self.tasks.all():
            d = task.data.dict(exclude_none=True)
            d['description'] = task.task_settings.description
            d['index'] = None
            if task.task_settings.task_type == 'path_pipe':
                d['index'] = task.task_settings.index  # type: ignore

            paused = any(
                [
                    task.task_settings.paused,
                    task.task_settings.paused_file,
                    task.task_settings.paused_file_global,
                ]
            )
            d['paused'] = paused
            d['slug'] = task.task_settings.slug
            d['type'] = task.task_settings.task_type
            response_media.append(d)

        # sort response
        response_media = sorted(response_media, key=lambda k: (k['type'], k['index']))

        response_media_page = response_media
        resp_data = {
            'totalCount': len(response_media),
            'count': len(response_media_page),
            'data': response_media_page,
        }
        resp.media = resp.response_model(resp_data, TaskPaginatedResponseModel, query_params)
