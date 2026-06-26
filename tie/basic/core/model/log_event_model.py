"""Log Event Model for log search endpoint."""

from pydantic import Field

from core.model.model_base import BaseModel
from core.model.response.paginated_response import PaginatedResponseModel


class LogEventModel(BaseModel):
    """Log Event Model"""

    date: str = Field(..., description='The date of the log event.')
    filename: str = Field(..., description='The filename of the log event.')
    level: str = Field(..., description='The log level of the log event.')
    message: str = Field(..., description='The message of the log event.')
    method_name: str = Field(..., description='The method name of the log event.')
    line_number: int = Field(..., description='The line number of the log event.')
    request_id: str | None = Field(..., description='The request ID of the log event.')
    task_name: str | None = Field(..., description='The name of the task for the log event.')
    thread_name: str = Field(..., description='The thread name of the log event.')
    log_file: str = Field(..., description='The log file of the log event.')


class LogEventPaginatedResponseModel(PaginatedResponseModel[LogEventModel]):
    """Pagination response for log events."""
