"""Converts the data into the ThreatConnect batch format."""

# standard library
import gzip
import json
from functools import cached_property
from pathlib import Path

# first-party
from core.model.tie.task_setting_pipe_model import TaskSettingPipeModel
from core.service.writing_service import WritingModel
from core.task.task_path_pipe_abc import TaskPathPipeABC


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
            'indicator',
            self.process_indicator,
        )

    def process_indicator(self, content, output_dir):
        """Process example data."""
        # TODO: There is no way to utilize the transforms currently.

        # if 'indicator' not in self.settings.sample_types:
        #     self.tcex.log.info('event=convert, action=skip, reason=event-not-enabled')
        #     return
        self.tcex.log.info('event=convert, action=writing-content, page-name=indicator')
        writer = WritingModel(page_name='indicator', output_dir=output_dir, force=True)
        self.writing_service.write_indicators(content, writer)

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
