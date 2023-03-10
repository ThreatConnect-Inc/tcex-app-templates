"""Class for /api/task endpoint"""
# standard library
import logging
from typing import Optional

# third-party
import falcon
from model import FilterParamModel
from pydantic import Field

from .resource_abc import ResourceABC

logger = logging.getLogger('tcex')


class PutQueryParamModel(FilterParamModel):
    """Params Model"""

    # task_name: str = Field(..., description='Filter by Task Name.')
    pause: Optional[bool] = Field(None, description='Pause or Resume the Task.')
    run: bool = Field(False, description='When True, run the Task.')


class TaskResource(ResourceABC):
    """Class for /api/task endpoint"""

    validation_models = {
        'PUT': {
            'request': {
                'query_params': PutQueryParamModel,
            }
        }
    }

    def __init__(self):
        """Initialize."""
        super().__init__()
        self.log = logger

    # pylint: disable=W0613
    def on_get(
        self, _req: 'falcon.Request', resp: 'falcon.Response', task_name: 'Optional[str]' = None
    ):
        """Handle GET requests."""
        if task_name:
            response_media = {}
            for task in self.tasks.all():
                if task.data.name.lower() == task_name.lower():
                    response_media = task.data.dict(exclude_none=True)
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
                    break
            else:
                resp.status = falcon.HTTP_404
        else:
            response_media = []
            for task in self.tasks.all():
                d = task.data.dict(exclude_none=True, exclude={'_ns'})
                d['description'] = task.task_settings.description
                d['index'] = None
                if task.task_settings.task_type == 'path_pipe':
                    d['index'] = task.task_settings.index

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
            response_media = sorted(
                response_media, key=lambda k: (k['type'], k['index'], k['name'])
            )

        # resp.text = json.dumps(data, default=str)
        resp.media = response_media

    def on_delete(self, _req: 'falcon.Request', resp: 'falcon.Response', task_name: str = None):
        """Handle DELETE requests.

        Kills the task with the given name, if it's running.
        """
        if not task_name:
            resp.status = falcon.HTTP_405
            return

        for task in self.tasks.all():
            if task_name.lower() in [task.data.name.lower(), task.task_settings.slug.lower()]:
                self.tasks.kill(task)
                resp.status = falcon.HTTP_204
                break
        else:
            resp.status = falcon.HTTP_404

    def on_put(self, req: 'falcon.Request', resp: 'falcon.Response', task_name: str = None):
        """Handle PUT requests."""
        for task in self.tasks.all():
            if task_name.lower() in [task.data.name.lower(), task.task_settings.slug.lower()]:
                if req.context.params.pause is not None:
                    task.task_settings.paused = req.context.params.pause
                elif req.context.params.run is True:
                    task.run_adhoc()
                resp.status = falcon.HTTP_204
                break
        else:
            resp.status = falcon.HTTP_404
