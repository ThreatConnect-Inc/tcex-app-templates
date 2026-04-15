"""Batch Submit"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TypeVar

from tcex import TcEx

from core.json_db import JsonDB
from core.task.task_path_pipe_abc import UploadError
from core.task.upload_abc import UploadABC
from model import JobRequestModel
from model.settings_model import SettingModel

T = TypeVar('T')


class UploadEgressABC(UploadABC, ABC):
    """Process to submit JSON files to TC batch API."""

    def __init__(self, settings: SettingModel, tcex: TcEx, db: JsonDB, sdk=None, pipeline=None):
        """Initialize the class."""
        super().__init__(settings, tcex, db, pipeline=pipeline)
        self.sdk = sdk

    @abstractmethod
    def process_file(self, file: Path, request: JobRequestModel):
        """Process the batch file and return the BatchSubmit instance and batch ID."""

    def process_file_wrapper(
        self,
        file: Path,
        request: JobRequestModel,
        output_dir: Path,  # noqa: ARG002
        failed_files: list[str],
    ) -> bool:
        """Handle batch file processing."""
        # Return True if successfully processed, False if not.
        try:
            if request.date_upload_failure and file.name not in request.upload_failed_files:
                self.log.info(f'action=skip-file, file={file.name}')
                return True
            self.process_file(file, request)
            self.update_heartbeat()  # Update the task heartbeat after processing
            return True
        except UploadError:
            self.log.exception(f'action="external-upload-error", file="{file.name}"')
            failed_files.append(file.name)
            return False

    @property
    def fields_to_reset(self) -> list[str]:
        """Return the fields to reset."""
        return ['count_upload_indicator_success', 'count_upload_error']
