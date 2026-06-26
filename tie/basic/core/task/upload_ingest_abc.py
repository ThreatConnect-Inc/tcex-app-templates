"""Batch Submit"""

import gzip
import inspect
import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import NamedTuple, TypeVar

import uuid6
from tcex.api.tc.v2.batch import BatchSubmit

from core.model.tie.batch_error_model import (
    JobBatchErrorIndexModel,
    UnknownBatchErrorModel,
    error_codes_model_map,
    error_codes_name_map,
)
from core.task.upload_abc import UploadABC
from model import JobRequestModel

T = TypeVar('T')


# Named tuple for write types
class WriteTypes(NamedTuple):
    """Named tuple for write types."""

    attribute: str
    tag: str
    security_label: str


# Custom exceptions
class BatchError(Exception):
    """Exception raised for general batch errors."""

    def __init__(self, message: str = 'An error occurred while processing the batch.'):
        """Init method for BatchError."""
        super().__init__(message)


class BatchCreateError(BatchError):
    """Exception raised for errors while creating a batch job."""

    def __init__(self, message: str = 'Failed to create batch job.'):
        """Init method for BatchCreateError."""
        super().__init__(message)


class BatchSubmitError(BatchError):
    """Exception raised for errors while submitting a batch job."""

    def __init__(self, message: str = 'Failed to submit batch job.'):
        """Init method for BatchSubmitError."""
        super().__init__(message)


class BatchPollError(BatchError):
    """Exception raised for errors while polling a batch job."""

    def __init__(self, message: str = 'Failed to poll batch job status.'):
        """Init method for BatchPollError."""
        super().__init__(message)


class UploadIngestABC(UploadABC, ABC):
    """Process to submit JSON files to TC batch API."""

    batch_error_codes = error_codes_name_map

    @abstractmethod
    def process_file(self, file: Path, request: JobRequestModel) -> tuple[BatchSubmit, int]:
        """Process the batch file and return the BatchSubmit instance and batch ID."""

    @property
    def fields_to_reset(self) -> list[str]:
        """Return the fields to reset."""
        return [
            'count_batch_error',
            'count_batch_group_success',
            'count_batch_indicator_success',
        ]

    def handle_batch_errors(self, batch_submit, batch_id, request, output_dir):
        """Handle batch errors."""
        try:
            batch_errors = self.get_batch_errors(batch_submit, batch_id)
        except Exception as e:
            raise BatchError from e
        try:
            self.report_batch_errors(batch_errors, request)
            self.write_batch_errors(batch_errors, request, output_dir)
        except Exception:
            self.log.exception('action="batch-errors", message="Failed to get batch errors"')

    def batch_error_code(self, code: str) -> str:
        """Return the description for the batch error code."""
        return self.batch_error_codes.get(code, 'Unknown')

    def get_batch_errors(self, batch_submit: BatchSubmit, batch_id: int) -> list[dict]:
        """Retrieve batch errors from the API."""
        self.log.debug(f'action="retrieve-batch-errors", status="start", batch-id="{batch_id}"')
        try:
            return batch_submit.errors(batch_id)
        except Exception as e:
            self.log.exception(
                f'action="retrieve-batch-errors", status="failed", batch-id="{batch_id}"'
            )
            msg = f'Error retrieving batch errors for ID {batch_id}'
            raise BatchError(msg) from e

    def report_batch_errors(self, batch_errors: list[dict], request: JobRequestModel) -> None:
        """Report and log batch errors."""
        ids = []
        for error in batch_errors:
            error_reason = error.get('errorReason', '')
            parsed_error = re.search(r'\w\s\((?P<code>0x[0-9]{4})\):\s(?P<reason>.*)', error_reason)
            code = parsed_error.group('code') if parsed_error else 'Unknown'
            reason = parsed_error.group('reason') if parsed_error else error_reason

            # Save the error to the database
            model_t = error_codes_model_map.get(code, UnknownBatchErrorModel)
            error_id = str(uuid6.uuid7())

            self.db.save(
                model_t(
                    id=error_id,
                    code=code,
                    message=self.batch_error_code(code),
                    reason=reason,
                    request_id=request.request_id,
                )
            )
            ids.append(error_id)
        try:
            index = self.db.load(JobBatchErrorIndexModel, request.request_id)
        except FileNotFoundError:
            index = JobBatchErrorIndexModel(request_id=request.request_id)

        index.error_ids = [*index.error_ids, *ids]

        self.db.save(index)

        if batch_errors:
            self._db_increment_counts(request, {'count_batch_error': len(batch_errors)})

    def write_batch_errors(
        self, batch_errors: list[dict], request: JobRequestModel, output_dir: Path
    ) -> None:
        """Write batch errors to a gzipped CSV file."""
        filename = f'{self.settings.file.separator}'.join(
            [request.request_id, 'batch-errors.csv.gz']
        )
        fqfn_out = output_dir / filename

        with gzip.open(fqfn_out, mode='wt', encoding='utf-8') as fh:
            for error in batch_errors:
                fh.write(f'{error.get("errorReason")}\n')

    def create_job_batch(self, batch_submit: BatchSubmit, halt_on_error: bool = False) -> int:
        """Create a new batch job and return the batch ID."""
        try:
            batch_id = batch_submit.create_job(halt_on_error=halt_on_error)
            self.log.debug(f'action="create-job-batch", status="success", batch-id="{batch_id}"')
        except ValueError as v:
            self.log.exception('action="create-job-batch", status="failure"')
            raise BatchCreateError from v

        if batch_id is None:
            self.log.error('action="create-job-batch", status="failure", reason="no-batch-id"')
            msg = 'Failed to create batch job, no batch ID returned.'
            raise BatchCreateError(msg)

        return batch_id

    @abstractmethod
    def get_batch_cleaner(self, batch_submit: BatchSubmit):
        """Return a BatchCleaner for content cleaning during batch submit."""

    def submit_batch(self, batch_submit: BatchSubmit, batch_id: int, batch_file: Path) -> None:
        """Submit the batch file to the API."""
        try:
            with gzip.open(batch_file, 'rt') as file:
                content = json.load(file)

            if content:
                kwargs = {'batch_id': batch_id, 'content': content}
                # clean_content is only supported in newer versions of tcex,
                # check the signature to avoid breaking older installations
                sig = inspect.signature(batch_submit.submit_data)
                if 'clean_content' in sig.parameters:
                    kwargs['clean_content'] = self.get_batch_cleaner(batch_submit)
                batch_response = batch_submit.submit_data(**kwargs)
                self.log.trace(
                    f'action="submit-batch", status="job-submit", response="{batch_response}"'
                )
                # Check for failed submission (tcex returns None on error without raising)
                if batch_response is None:
                    raise BatchSubmitError(  # noqa: TRY301
                        f'Batch data submission failed for batch ID {batch_id}. '
                        'Check logs for error details (likely file size exceeded limits).'
                    )
        except BatchSubmitError:
            raise  # Re-raise BatchSubmitError without wrapping
        except Exception as e:
            self.log.exception(f'action="submit-batch", status="failure", batch-id="{batch_id}"')
            msg = f'Error submitting batch ID {batch_id}'
            raise BatchSubmitError(msg) from e

    def poll_batch(self, batch_submit: BatchSubmit, batch_id: int) -> dict:
        """Poll the batch status and raise an error if not successful."""
        try:
            poll_status = self._batch_poll(batch_submit, batch_id)
            if poll_status.get('status') != 'Success':
                msg = f'Error polling batch ID {batch_id}'
                raise BatchPollError(msg)  # noqa: TRY301
            return poll_status.get('data', {}).get('batchStatus', {})
        except Exception as e:
            self.log.exception(f'action="poll-batch", status="failure", batch-id="{batch_id}"')
            msg = f'Error polling batch ID {batch_id}'
            raise BatchPollError(msg) from e

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

    def process_file_wrapper(
        self,
        file: Path,
        request: JobRequestModel,
        output_dir: Path,
        failed_files: list[str],
    ) -> bool:
        """Handle batch file processing."""
        # Return True if successfully processed, False if not.
        try:
            if request.date_upload_failure and file.name not in request.upload_failed_files:
                self.log.info(f'action=skip-file, file={file.name}')
                return True
            self.update_heartbeat()  # Update the task heartbeat after processing
            batch_submit, batch_id = self.process_file(file, request)
            if batch_submit and batch_id:
                self.handle_batch_errors(batch_submit, batch_id, request, output_dir)
            self.update_heartbeat()  # Update the task heartbeat after processing
            return True
        except BatchSubmitError:
            self.log.exception(f'action="batch-upload-error", file="{file.name}"')
            # Try to split oversized files
            split_files = self._try_split_oversized_file(file)
            if split_files:
                failed_files.extend(split_files)
            else:
                failed_files.append(file.name)
            return False
        except BatchError:
            self.log.exception(f'action="batch-upload-error", file="{file.name}"')
            failed_files.append(file.name)
            return False

    def _try_split_oversized_file(self, file: Path) -> list[str] | None:
        """Split an oversized file into two smaller files.

        Args:
            file: Path to the oversized .json.gz file

        Returns:
            List of new filenames if split successful, None otherwise.
        """
        try:
            with gzip.open(file, 'rt') as f:
                data = json.load(f)

            # Check if there's data to split
            total_items = sum(len(v) for v in data.values() if isinstance(v, list))
            if total_items <= 1:
                self.log.warning(
                    f'action="skip-split", file="{file.name}", reason="not-enough-items"'
                )
                return None

            # Split each list in half
            half1, half2 = {}, {}
            for key, items in data.items():
                if isinstance(items, list):
                    mid = len(items) // 2
                    half1[key] = items[:mid]
                    half2[key] = items[mid:]
                else:
                    # Non-list values go to both halves
                    half1[key] = items
                    half2[key] = items

            # Generate new filenames
            base = file.stem.replace('.json', '')
            file1 = file.parent / f'{base}_split1.json.gz'
            file2 = file.parent / f'{base}_split2.json.gz'

            # Write split files
            for path, content in [(file1, half1), (file2, half2)]:
                with gzip.open(path, 'wt') as f:
                    json.dump(content, f)

            # Remove original
            file.unlink()

            self.log.info(
                f'action="split-oversized-file", original="{file.name}", '
                f'split_into=["{file1.name}", "{file2.name}"], items={total_items}'
            )

            return [file1.name, file2.name]

        except Exception:
            self.log.exception(f'action="split-file-error", file="{file.name}"')
            return None

    @property
    def write_type_mapping(self) -> dict[str, WriteTypes]:
        """Write type mapping."""
        return {}

    def _reset_counts(self, request: JobRequestModel) -> None:
        """Reset counts for the given request."""
        self.log.debug(f'action="reset-counts", request-id="{request.request_id}"')
        self._db_reset_counts(
            request,
            [
                'count_batch_error',
                'count_batch_group_success',
                'count_batch_indicator_success',
            ],
        )

    def _batch_poll(self, batch_submit: BatchSubmit, batch_id: int) -> dict:
        """Poll the batch status."""
        self.log.debug(f'action="poll-batch", status="start", batch-id="{batch_id}"')
        poll_status = batch_submit.poll(batch_id=batch_id)

        log_message = (
            f'action="poll-batch", status="in-progress", poll-status="{poll_status.get("status")}",'
            f'batch-id="{batch_id}"'
        )
        self.log.info(log_message)
        return poll_status
