"""."""

from tcex.logger.trace_logger import TraceLogger

from core.dao.job_dao import JobRequestDAO
from core.json_db import JsonDB
from core.task.tasks import Tasks
from model.settings_model import SettingModel


def log_running_tasks(db: JsonDB, settings: SettingModel, log: TraceLogger):
    """Log running tasks."""
    dao = JobRequestDAO(db, settings)
    throttle_statuses = [
        settings.job.status_cancelled,
        settings.job.status_failed,
        settings.job.status_pending,
    ]
    throttle_statuses.extend(Tasks.status_final)

    running_tasks = [
        {r.request_id: r.status} for r in dao.get_all() if r.status.lower() not in throttle_statuses
    ]
    log.debug(
        f'task-event=log-running-tasks, running_tasks={running_tasks},'
        f' final-status={Tasks.status_final}'
    )
    return running_tasks
