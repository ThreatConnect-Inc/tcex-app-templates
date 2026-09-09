"""Egress Upload ABC — base class for uploading converted data to external targets."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

from tcex import TcEx

from core.json_db import JsonDB
from core.task.task_path_pipe_abc import UploadError
from core.task.upload_abc import UploadABC
from model import JobRequestModel
from model.settings_model import SettingModel


class UploadEgressABC(UploadABC, ABC):
    """Egress upload base class with a transform pipeline.

    Transforms are callables that receive a single dict and return a modified
    dict, or ``None`` to drop the item. Register transforms in ``__init__``
    (e.g. TTL resolution, field enrichment) and call :meth:`apply_transforms`
    before uploading each batch.
    """

    def __init__(self, settings: SettingModel, tcex: TcEx, db: JsonDB, sdk=None, pipeline=None):
        """Initialize the class."""
        super().__init__(settings, tcex, db, pipeline=pipeline)
        self.sdk = sdk
        self._transforms: list[Callable[[dict], dict | None]] = []

    def register_transform(self, fn: Callable[[dict], dict | None]) -> None:
        """Register a transform applied to each object before upload.

        Args:
            fn: A callable that receives a dict and returns the modified dict,
                or ``None`` to drop the item from the batch.
        """
        self._transforms.append(fn)

    def apply_transforms(self, objects: list[dict]) -> list[dict]:
        """Apply all registered transforms to a list of objects.

        Items are dropped when any transform returns ``None``.
        """
        result: list[dict] = []
        for obj in objects:
            for fn in self._transforms:
                obj = fn(obj)
                if obj is None:
                    break
            if obj is not None:
                result.append(obj)
        return result

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
