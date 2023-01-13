"""Class for /api/task/status endpoint"""
# standard library
from typing import TYPE_CHECKING

# first-party
from tasks import TaskPathPipeABC

from .resource_abc import ResourceABC

if TYPE_CHECKING:
    # third-party
    import falcon


class TaskStatusResource(ResourceABC):
    """Class for /api/task/status endpoint

    Return the possible status options for a task.
    """

    def on_get(self, _req: 'falcon.Request', resp: 'falcon.Response'):
        """Handle GET requests."""
        status = []
        for task in self.tasks.all():
            if isinstance(task, TaskPathPipeABC):
                status.append(task.task_settings.status_active.title())
                status.append(task.task_settings.status_complete.title())
        resp.media = sorted(status)
