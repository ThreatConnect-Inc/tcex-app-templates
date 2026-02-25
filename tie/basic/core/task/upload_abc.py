"""Batch Submit"""

# standard library
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NamedTuple, TypeVar

# third-party
from tcex import TcEx

# first-party
from core.json_db import JsonDB
from core.task.task_path_pipe_abc import TaskPathPipeABC, UploadError, UploadRetryError
from model import JobRequestModel
from model.settings_model import SettingModel

T = TypeVar('T')


# Named tuple for write types
class WriteTypes(NamedTuple):
    """Named tuple for write types."""

    attribute: str
    tag: str
    security_label: str


class UploadABC(TaskPathPipeABC, ABC):
    """Process to submit JSON files to TC batch API."""

    def __init__(
        self,
        settings: SettingModel,
        tcex: TcEx,
        db: JsonDB,
        *,
        pipeline=None,
    ):
        """Initialize the class."""
        super().__init__(settings, tcex, db)
        self.pipeline = pipeline

    def increment_counts(self, request: JobRequestModel, batch_status: dict) -> None:
        """Increment the counts for successful batches."""
        group_count = batch_status.get('successGroupCount', 0)
        indicator_count = batch_status.get('successIndicatorCount', 0)

        log_message = (
            'action="submit-batch", status="update-counts", '
            f'success-group-count="{group_count}", success-indicator-count="{indicator_count}"'
        )
        self.log.info(log_message)

        self._db_increment_counts(
            request,
            {
                'count_batch_group_success': group_count,
                'count_batch_indicator_success': indicator_count,
            },
        )

    def handle_run_error(
        self, request_id: str, request_dir: Path, exception: Exception | None = None
    ):
        """Handle upload errors - mark as failed (no retry from Download)."""
        self._task_complete_failed(request_id, request_dir)

    def launch_preflight_checks(self):
        """Launch preflight checks."""
        if self.ns.unrecoverable_failure is True:
            return
        request_dir = self._next_request_dir
        if request_dir is None:
            return
        request_id = self._get_request_id(request_dir)
        self.log.info(
            f'action="preflight-checks", request-id="{request_id}", task="{self.task_settings.name}'
        )
        request = self.job_dao.get(request_id)
        if request.date_upload_failure:
            now = datetime.now(UTC)
            delta = now - request.date_upload_failure
            msg = (
                f'action=batch-failure-detected. delta={delta}, '
                f'retries={request.count_upload_retries}, '
                f'date={request.date_upload_failure}, '
                f'failed_files={request.upload_failed_files}'
            )
            self.log.info(msg)
            if delta < timedelta(minutes=5):
                self.log.info('action=throttle')
                return
        self.launch(request_id, request_dir)

    @abstractmethod
    def process_file_wrapper(
        self, file: Path, request: JobRequestModel, output_dir: Path, failed_files: list[str]
    ) -> bool:
        """Handle file processing.

        Args:
            file: Path to the file to process
            request: The job request model
            output_dir: Output directory for any generated files
            failed_files: List to append failed filenames to (modified in place)

        Returns:
            True if successfully processed, False if not
        """

    def run(self, request_id: str, input_dir: Path, output_dir: Path) -> None:
        """Run the task to process all files."""
        self.log.info(f'action="run-task", status="start", request-id="{request_id}"')

        request = self.job_dao.get(request_id)
        self._reset_counts(request)

        files = sorted(input_dir.iterdir())
        failed_files = []
        self.log.debug(f'action="run-task", status="processing-files", files="{files}"')
        for counter, file in enumerate(files, start=1):
            process = f'({counter}/{len(files)})'
            self.log.debug(f'action="processing-file", file="{file.name}", process="{process}"')
            self.process_file_wrapper(file, request, output_dir, failed_files)

        self.handle_upload_failure(failed_files, request)
        self.log.info(f'action="run-task", status="complete", request-id="{request_id}"')

    def handle_upload_failure(
        self, failed_files: list[str], request: JobRequestModel, max_retries: int = 3
    ) -> None:
        """Handle batch upload failure."""
        if not failed_files:
            return

        for file in failed_files:
            self.log.warning(f'action="batch-upload-error", file="{file}"')
        request.date_upload_failure = datetime.now(UTC)
        request.upload_failed_files = failed_files
        if request.count_upload_retries > max_retries:
            self.job_dao.save(request)
            msg = 'Max retries exceeded'
            raise UploadError(msg)
        request.count_upload_retries += 1
        self.job_dao.save(request)
        msg = (
            'action="batch-upload-error", '
            f'files="{failed_files}", '
            f'retries="{request.count_upload_retries}", '
            f'max_retries={max_retries}, '
            f'date_batch_failure="{request.date_upload_failure}"'
        )
        raise UploadRetryError(msg)

    @property
    def fields_to_reset(self) -> list[str]:
        """Fields to reset."""
        return []

    def _reset_counts(self, request: JobRequestModel) -> None:
        """Reset counts for the given request."""
        self.log.debug(f'action="reset-counts", request-id="{request.request_id}"')
        self._db_reset_counts(request, self.fields_to_reset)
