"""Class for /api/task endpoint"""

import urllib.parse

import falcon
from pydantic import Field
from spectree import Response

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_task
from core.api.validation.models.query_param_filter_model import QueryParamFilterModel
from core.api.validation.models.query_param_model import QueryParamModel
from core.model.response.paginated_response import PaginatedResponseModel
from core.model.response.response_model import ResponseModel
from core.model.tie.task_setting_model import TaskSettingModel


class PutQueryParamModel(QueryParamModel):
    """Params Model"""

    # task_name: str = Field(..., description='Filter by Task Name.')
    pause: bool | None = Field(default=None, description='Pause or Resume the Task.')
    run: bool = Field(default=False, description='When True, run the Task.')


class TaskPaginatedResponseModel(PaginatedResponseModel[TaskSettingModel]):
    """Model Definition"""


class TaskItem(EndpointBase):
    """Class for /api/task endpoint"""

    @spec.validate(
        query=QueryParamFilterModel,
        resp=Response(HTTP_200=ResponseModel),
        skip_validation=True,
        tags=[tag_task],
    )
    def on_get(
        self,
        _req: FalconRequest,
        resp: FalconResponse,
        task_name: str,
        query_params: QueryParamFilterModel,
    ):
        """Get task details."""
        task_name = urllib.parse.unquote(task_name)
        for task in self.tasks.all():
            if task.data.name.lower() == task_name.lower():
                response_media = task.data.model_dump(exclude_none=True)
                response_media['description'] = task.task_settings.description
                paused = any(
                    [
                        task.task_settings.paused,
                        task.task_settings.paused_file,
                        task.task_settings.paused_file_global,
                    ]
                )
                response_media['paused'] = paused
                response_media['slug'] = task.task_settings.slug
                resp.media = resp.response_model(
                    {'data': response_media}, ResponseModel, query_params
                )
                break
        else:
            resp.status = falcon.HTTP_404

    @spec.validate(
        resp=Response('HTTP_204'),
        skip_validation=True,
        tags=[tag_task],
    )
    def on_delete(self, _req: FalconRequest, resp: FalconResponse, task_name: str):
        """Kill running task."""
        if not task_name:
            resp.status = falcon.HTTP_405
            return

        task_name = urllib.parse.unquote(task_name)
        for task in self.tasks.all():
            if task_name.lower() in [
                task.data.name.lower(),
                task.task_settings.slug.lower(),
            ]:
                self.tasks.kill(task)
                resp.status = falcon.HTTP_204
                break
        else:
            resp.status = falcon.HTTP_404

    @spec.validate(
        query=PutQueryParamModel,
        resp=Response('HTTP_204'),
        skip_validation=True,
        tags=[tag_task],
    )
    def on_put(
        self,
        _req: FalconRequest,
        resp: FalconResponse,
        task_name: str,
        query_params: PutQueryParamModel,
    ):
        """Execute an action on a task."""
        if not task_name:
            resp.status = falcon.HTTP_405
            return
        task_name = urllib.parse.unquote(task_name)
        for task in self.tasks.all():
            if task_name.lower() in [
                task.data.name.lower(),
                task.task_settings.slug.lower(),
            ]:
                if query_params.pause is not None:
                    task.task_settings.paused = query_params.pause
                elif query_params.run is True:
                    task.run_adhoc()
                resp.status = falcon.HTTP_204
                break
        else:
            resp.status = falcon.HTTP_404
