"""Task Module"""

from functools import cached_property
from pathlib import Path

from core.model.tie.task_setting_pipe_model import TaskSettingPipeModel
from core.service.managers.operation_managers import ManagerBuilder
from core.task.download_abc import DownloadABC
from model.job_request_model import JobRequestModel


class Download(DownloadABC):
    """Task Module for downloading data."""

    def download(self, output_dir: Path, request: JobRequestModel):  # noqa: ARG002
        """Download resources from provider."""
        indicators = self.tcex.api.tc.v3.indicators(params={'resultLimit': 10})
        max_indicators = 10
        with (
            ManagerBuilder()
            .with_file_writer_manager(out_dir=output_dir)
            .with_request_counts_manager('count_download_indicator')
            .build()
        ) as accept:
            for counter, indicator in enumerate(indicators):
                if counter >= max_indicators:
                    break
                accept(
                    indicator.model.model_dump(
                        by_alias=True, exclude_none=True, exclude_unset=True
                    ),
                    data_type='indicator',
                )

    @cached_property
    def task_settings(self) -> TaskSettingPipeModel:
        """Return the task settings."""
        name = 'Download'
        if self.pipeline:
            name = f'{name} - {self.pipeline.title()}'
        return TaskSettingPipeModel(
            base_path=self.settings.base_path,
            date_field_start='date_download_start',
            date_field_complete='date_download_complete',
            description='Downloads indicators from ThreatConnect.',
            max_execution_minutes=20,
            name=name,
        )
