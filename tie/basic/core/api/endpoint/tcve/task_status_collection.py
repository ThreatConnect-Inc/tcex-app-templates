"""Task status collection resource for /api/task/status endpoint."""

# third-party
import falcon

# first-party
from core.api.endpoint.endpoint_base_abc import EndpointBaseABC
from core.task.task_path_pipe_abc import TaskPathPipeABC


class TaskStatusCollection(EndpointBaseABC):
    """Class for /api/task/status endpoint.

    Returns the possible status options for a task.
    """

    def on_get(self, _req: falcon.Request, resp: falcon.Response):
        """Handle GET requests — return sorted list of all possible task statuses."""
        status = ['Failed', 'Pending']
        for task in self.tasks.all():
            if isinstance(task, TaskPathPipeABC):
                status.append(task.task_settings.status_active.title())
                status.append(task.task_settings.status_complete.title())
        resp.media = {'data': sorted(status)}
