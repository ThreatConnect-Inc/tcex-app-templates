"""Batch Submit"""
# standard library
import gzip
import json
import re
from typing import TYPE_CHECKING, Dict

# third-party
from schema import BatchErrorSchema, JobRequestSchema
from tasks.model import TaskSettingPipeModel
from tasks.task_path_pipe_abc import TaskPathPipeABC
from tcex.backports import cached_property

if TYPE_CHECKING:
    # standard library
    from pathlib import Path

    # third-party
    from tcex.api.tc.v2.batch import BatchSubmit


class UploadPathPipe(TaskPathPipeABC):
    """Process to submit JSON files to TC batch API."""

    @staticmethod
    def _batch_error_codes(code: str) -> Dict[str, str]:
        """Return static list of Batch error codes and short description"""
        _error_codes = {
            '0x1001': 'General Error',
            '0x1002': 'Permission Error',
            '0x1003': 'JsonSyntax Error',
            '0x1004': 'Internal Error',
            '0x1005': 'Invalid Indicator Error',
            '0x1006': 'Invalid Group Error',
            '0x1007': 'Item Not Found Error',
            '0x1008': 'Indicator Limit Error',
            '0x1009': 'Association Error',
            '0x100A': 'Duplicate Item Error',
            '0x100B': 'File IO Error',
            '0x2001': 'Indicator Partial Loss Error',
            '0x2002': 'Group Partial Loss Error',
            '0x2003': 'File Hash Merge Error',
            '0x3001': 'File Hash Merge Error',
        }
        return _error_codes.get(code, 'Unknown')

    def _batch_errors(
        self, batch_submit: 'BatchSubmit', batch_id: int, request_id: str, output_dir: 'Path'
    ) -> list:
        """Return batch errors."""
        batch_errors = []
        try:
            batch_errors = batch_submit.errors(batch_id)
            for error in batch_errors:
                error_reason = error.get('errorReason')
                parsed_error = re.search(
                    r'\w\s\((?P<code>0x[0-9]{4})\):\s(?P<reason>.*)', error_reason
                )
                code = parsed_error.group('code') if parsed_error else 'Unknown'
                record = self.db.create_record(
                    BatchErrorSchema,
                    {
                        'code': code,
                        'message': self._batch_error_codes(code),
                        'reason': parsed_error.group('reason') if parsed_error else error_reason,
                        'request_id': request_id,
                    },
                    'Unexpected error creating batch error record.',
                )
                self.db.add_record(
                    self.session, record, 'Unexpected error adding batch error record.'
                )

            if batch_errors:
                self._db_increment_counts(request_id, {'count_batch_error': len(batch_errors)})

                # write errors to disk
                filename = f'{self.settings.file_config_separator}'.join(
                    [request_id, 'batch-errors.csv.gz']
                )
                fqfn_out = output_dir / filename
                with gzip.open(fqfn_out, mode='wt', encoding='utf-8') as fh:
                    for error in batch_errors:
                        fh.write(f'''{error.get('errorReason')}\n''')

        except RuntimeError:
            raise
        except Exception:
            self.log.exception('failure=failed-retrieving-batch-errors')

        return batch_errors

    def _batch_poll(self, batch_submit: 'BatchSubmit', batch_id: int) -> dict:
        """Poll for batch status."""
        poll_status = {}
        try:
            poll_status = batch_submit.poll(batch_id=batch_id)
            self.log.info(
                f'task-event-path-pipe=batch-submit-poll-status, poll-status={poll_status}'
            )
        except Exception:
            self.log.exception('failure=batch-submit, exception=poll-failed')

        return poll_status

    def _reset_counts(self, request_id: str):
        """Reset counts for request_id."""
        self._db_reset_counts(
            request_id,
            ['count_batch_error', 'count_batch_group_success', 'count_batch_indicator_success'],
        )

    def _submit_batch(self, batch_file: 'Path', request_id: str, output_dir: 'Path'):
        """Submit the batch file."""
        action = 'Create'
        batch_id = None
        batch_submit = self.tcex.v2.batch_submit(
            action='Create',
            owner=self.settings.owner,
            tag_write_type='Append',
            security_label_write_type='Append',
            playbook_triggers_enabled=True,
        )
        try:
            batch_id = batch_submit.create_job(halt_on_error=False)
            self.log.trace(f'task-pipe-path-event=create-job, batch-id={batch_id}')
        except ValueError as v:
            self.log.exception('failure=batch-create')

            # we only want to pull out "structured" exceptions created with handle_error in tcex.
            if len(v.args) == 2:
                record = self.db.create_record(
                    BatchErrorSchema,
                    {
                        'code': v.args[0],
                        'message': v.args[1],
                        'reason': v.args[1],
                        'request_id': request_id,
                    },
                    'Unexpected error creating batch error record.',
                )
                self.db.add_record(
                    self.session, record, 'Unexpected error adding batch error record.'
                )
            else:
                raise

        # ensure batch id is returned
        if batch_id is None:
            # assuming this failure is temporary
            self.log.error(
                'task-pipe-path-event=batch-submit-create-job, exception=no-batch-id-returned'
            )
            raise RuntimeError('No batch id returned.')

        # load and send batch content
        try:
            content = gzip.open(batch_file, 'rt').read()
            data = json.loads(content)
            if data:
                batch_response = batch_submit.submit_data(
                    batch_id=batch_id, content=json.loads(content)
                )
                self.log.trace(
                    f'task-pipe-path-event=batch-submit-content, '
                    f'batch-response={batch_response}'
                )
        except Exception as ex:
            self.log.error(f'task-pipe-path-event=batch-submit-error, exception={ex}')
            raise

        try:
            # poll for batch status
            poll_status = self._batch_poll(batch_submit, batch_id)
            if poll_status.get('status') != 'Success':
                return

            # get indicator counts from response instead of json
            # loading file data. this should keep memory usage lower.
            batch_status = poll_status.get('data', {}).get('batchStatus', {})

            success_group_count = batch_status.get('successGroupCount', 0)
            success_indicator_count = batch_status.get('successIndicatorCount', 0)

            # update count and possible status/date
            if action == 'Create':
                self.tcex.log.info(
                    f'Updating batch counts: {request_id}, '
                    f'{success_group_count}, {success_indicator_count}'
                )

                # update request counts
                self._db_increment_counts(
                    request_id,
                    {
                        'count_batch_group_success': success_group_count,
                        'count_batch_indicator_success': success_indicator_count,
                    },
                )
        except Exception:
            self.log.exception('failure=failed-submitting-batch')
            raise

        # handle batch_errors
        self._batch_errors(batch_submit, batch_id, request_id, output_dir)

    def run(self, request_id: str, input_dir: 'Path', output_dir: 'Path'):
        """Run the task."""
        # reset counts in case previous attempt failed
        self._reset_counts(request_id)

        for batch_file in sorted(input_dir.iterdir()):
            # update the task heartbeat
            self.update_heartbeat()

            self._submit_batch(batch_file, request_id, output_dir)

    @cached_property
    def task_settings(self) -> 'TaskSettingPipeModel':
        """Return the task settings."""

        return TaskSettingPipeModel(
            base_path=self.settings.base_path,
            date_field_start=JobRequestSchema.date_upload_start,
            date_field_complete=JobRequestSchema.date_upload_complete,
            description='Uploads the threat intel data into the ThreatConnect Platform.',
            max_execution_minutes=30,
            name='Upload',
            # schedule_period=10,
            # schedule_unit='seconds',
        )
