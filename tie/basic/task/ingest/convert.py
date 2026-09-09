"""Converts the data into the ThreatConnect batch format."""

import gzip
import json
from functools import cached_property
from pathlib import Path

from core.model.tie.task_setting_pipe_model import TaskSettingPipeModel
from core.service.writing_service import WritingModel
from core.task.task_path_pipe_abc import TaskPathPipeABC
from more.transform.sample_transform import SampleTransform


class Convert(TaskPathPipeABC):
    """Task"""

    def __init__(self, settings, tcex, db, *, pipeline=None):
        """Initialize class properties."""
        super().__init__(settings, tcex, db)
        self.request = None
        self.pipeline = pipeline

    def run(self, request_id: str, input_dir: Path, output_dir: Path):
        """Run the task."""
        self.tcex.log.info(f'event=convert, action=running-task, request_id={request_id}')
        self.request = self.job_dao.get(request_id)
        self.writing_service.request = self.request
        self.process_files(
            input_dir,
            output_dir,
            'event',
            self.process_event,
        )

    def process_event(self, content, output_dir):
        """Process example data.

        Read through `settings.app_settings` at use time, never cached on the instance —
        a settings save rebinds that record, so a Sample Types change takes effect on the
        next file rather than on the next restart.
        """
        # Compared case-insensitively on purpose. The record holds whatever case its
        # source used: seeded from the app inputs it is lowercased by
        # `AppBaseModel.validate_sample_types`, saved from the Settings form it carries the
        # `all_sample_types` catalogue's case ('Event'). A literal comparison would match
        # one of those and silently skip the other — a no-match, not an error.
        enabled = {str(entry).strip().lower() for entry in self.settings.app_settings.sample_types}
        if 'event' not in enabled:
            self.tcex.log.info('event=convert, action=skip, reason=event-not-enabled')
            return
        self.tcex.log.info('event=convert, action=process-event')

        transforms = self.tcex.api.tc.ti_transforms(
            content, [SampleTransform(self.settings, self.tcex).transform]
        )
        data = transforms.batch
        if not self._has_ti_data(data):
            self.tcex.log.info('event=convert, action=skip, reason=empty-transform')
            return

        self.tcex.log.info('event=convert, action=writing-batch, page-name=event')
        writer = WritingModel(page_name='event', output_dir=output_dir, force=True)
        self.writing_service.write_batch(data, writer)

    def process_files(self, input_dir: Path, output_dir: Path, prefix: str, *processors):
        """Process files with the given prefix using specified processors."""
        log_message = (
            'event=convert, action=process-files, '
            f'prefix={prefix}, processors={[p.__name__ for p in processors]}'
        )
        self.tcex.log.info(log_message)
        for file in sorted(input_dir.glob(f'*{prefix}*')) or []:
            self.update_heartbeat()
            with gzip.open(file, mode='rt', encoding='utf-8') as fh:
                content = json.load(fh)

            log_message = (
                'event=convert, action=process-file, '
                f'file_name={file.name}, '
                f'record_count={len(content)}'
            )
            self.tcex.log.info(log_message)
            for processor in processors:
                processor(content, output_dir)

    @cached_property
    def task_settings(self) -> TaskSettingPipeModel:
        """Return the task settings for this task."""
        name = 'Convert'
        if self.pipeline:
            name = f'{name} - {self.pipeline.title()}'
        return TaskSettingPipeModel(
            base_path=self.settings.base_path,
            date_field_start='date_convert_start',
            date_field_complete='date_convert_complete',
            description='Converts the data into the ThreatConnect batch format.',
            max_execution_minutes=60,
            name=name,
            schedule_period=30,
            schedule_unit='seconds',
        )
