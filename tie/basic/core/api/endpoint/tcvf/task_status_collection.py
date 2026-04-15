"""Class for /api/task/status endpoint"""

from spectree import Response

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_task
from core.api.validation.models.query_param_filter_model import QueryParamFilterModel
from core.model.response.response_model import ResponseModel
from core.task.task_path_pipe_abc import TaskPathPipeABC

# TODO: @cblades - See if this can be removed


class TaskStatusCollection(EndpointBase):
    """Class for /api/task/status endpoint

    Return the possible status options for a task.
    """

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
        query_params: QueryParamFilterModel,
    ):
        """Handle GET requests."""
        status = []
        for task in self.tasks.all():
            if isinstance(task, TaskPathPipeABC):
                status.append(task.task_settings.status_active.title())
                status.append(task.task_settings.status_complete.title())

        status += ['Failed', 'Pending']

        status.sort()
        resp.media = resp.response_model({'data': status}, ResponseModel, query_params)
