"""Task collection resource for /api/task and /api/task/{task_name} endpoints."""

import urllib.parse

# third-party
import falcon

# first-party
from core.api.endpoint.endpoint_base_abc import EndpointBaseABC
from core.task.task_abc import TaskItemModel, TaskPaginatedResponseModel


class TaskCollection(EndpointBaseABC):
    """Class for /api/task and /api/task/{task_name} endpoints."""

    @staticmethod
    def _task_item(task, *, include_type_index: bool) -> TaskItemModel:
        """Build a TaskItemModel for the given task."""
        data = task.data
        paused = any(
            [
                task.task_settings.paused,
                task.task_settings.paused_file,
                task.task_settings.paused_file_global,
            ]
        )

        task_type = None
        index = None
        if include_type_index:
            task_type = task.task_settings.task_type
            if task_type == 'path_pipe':
                index = task.task_settings.index

        return TaskItemModel(
            process=data.process,
            name=data.name,
            max_execution_minutes=data.max_execution_minutes,
            schedule_period=data.schedule_period,
            schedule_unit=data.schedule_unit,
            description=task.task_settings.description,
            paused=paused,
            slug=task.task_settings.slug,
            type=task_type,
            index=index,
        )

    def on_get(
        self,
        req: falcon.Request,
        resp: falcon.Response,
        task_name: str | None = None,
    ):
        """Handle GET requests — return task(s) data."""
        by_alias = req.get_param_as_bool('by_alias', default=False)

        if task_name:
            task_name = urllib.parse.unquote(task_name)
            item: TaskItemModel | None = None
            for task in self.tasks.all():
                if task.data.name.lower() == task_name.lower():
                    item = self._task_item(task, include_type_index=False)
                    break

            if item is None:
                resp.status = falcon.HTTP_404
                return

            resp.media = item.dict(by_alias=by_alias, exclude_none=True)
        else:
            items = [self._task_item(task, include_type_index=True) for task in self.tasks.all()]
            # `index` is None for any task that is not a path_pipe, and for a path_pipe
            # registered outside `Tasks.add_task_path_pipe` (which is what assigns it).
            # Mixing None and int in the sort key raises TypeError and 500s this endpoint,
            # so unindexed tasks sort ahead of indexed ones within their type.
            items = sorted(
                items,
                key=lambda i: (i.type, i.index if i.index is not None else -1, i.name),
            )

            response = TaskPaginatedResponseModel(
                data=items,
                count=len(items),
                total_count=len(items),
            )
            resp.media = response.dict(by_alias=by_alias, exclude_none=True)

    def on_delete(
        self,
        _req: falcon.Request,
        resp: falcon.Response,
        task_name: str | None = None,
    ):
        """Handle DELETE requests — kill a named task if it is running."""
        if not task_name:
            resp.status = falcon.HTTP_405
            return
        task_name = urllib.parse.unquote(task_name)

        for task in self.tasks.all():
            if task_name.lower() in [task.data.name.lower(), task.task_settings.slug.lower()]:
                self.tasks.kill(task)
                resp.status = falcon.HTTP_204
                break
        else:
            resp.status = falcon.HTTP_404

    def on_put(
        self,
        req: falcon.Request,
        resp: falcon.Response,
        task_name: str | None = None,
    ):
        """Handle PUT requests — pause/resume or trigger an ad-hoc run of a named task."""
        if not task_name:
            resp.status = falcon.HTTP_405
            return
        task_name = urllib.parse.unquote(task_name)

        pause = req.get_param_as_bool('pause')
        run = req.get_param_as_bool('run', default=False)

        for task in self.tasks.all():
            if task_name.lower() in [task.data.name.lower(), task.task_settings.slug.lower()]:
                if pause is not None:
                    task.task_settings.paused = pause
                elif run is True:
                    task.run_adhoc()
                resp.status = falcon.HTTP_204
                break
        else:
            resp.status = falcon.HTTP_404
