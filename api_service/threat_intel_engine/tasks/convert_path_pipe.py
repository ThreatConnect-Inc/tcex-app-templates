"""Task"""
# standard library
import gzip
import json
from typing import TYPE_CHECKING

# third-party
from more.transforms import IndicatorTransform
from schema import JobRequestSchema
from tasks.model import TaskSettingPipeModel
from tasks.task_path_pipe_abc import TaskPathPipeABC
from tcex.backports import cached_property

if TYPE_CHECKING:
    # standard library
    from pathlib import Path
    from typing import Dict

    # third-party
    from pydantic import BaseModel
    from tcex import TcEx


class ConvertPathPipe(TaskPathPipeABC):
    """Task Path Pipe Module

    Task Flow:

    1. launch_preflight_checks - run pre-flight checks before launching task (run method)
    2. launch - launch task, typically as multiprocessing.Process
    3. run - task entry point

    The convert task gets "jobs" from the input dir, which is populated by the upstream download
    task. This task writes output data to the working directory of the next task. The directory
    structure is automatically handled by the TaskPathPipeABC class and the add_task_path_pipe
    method in tasks.py (called from app.py).
    """

    def __init__(self, settings: 'BaseModel', tcex: 'TcEx'):
        """Initialize class properties."""
        super().__init__(settings, tcex)

        # properties

    @staticmethod
    def _has_ti_data(data: dict) -> bool:
        """Return True if data has TI data."""
        if data.get('group') or data.get('indicator'):
            return True
        return False

    def run(self, _: str, input_dir: 'Path', output_dir: 'Path'):
        """Run the task.

        The request_id, input_dir, and output_dir are passed to the run method of all task. For
        the convert task input comes from the input_dir. The output_dir is used to write the
        converted data to disk and is the input directory for the next task in the pipe.
        """

        # get an instance of the transform classes, this class will take
        # the provider data and convert it to ThreatConnect batch format.
        indicator_transform = IndicatorTransform(self.settings, self.tcex).transform

        # iterate over all files in the input directory, which should be the output of the download
        # task. The files are sorted to ensure the data is processed in the correct order.
        for domain_file in sorted(input_dir.glob('*indicators*')) or []:
            # by default the files are gzipped, so open the file in text mode and load the json
            with gzip.open(domain_file, mode='rt', encoding='utf-8') as fh:
                contents = json.load(fh)

            # if the file is not empty, then transform the data and write the results to disk.
            if contents:
                transforms = self.tcex.api.tc.ti_transforms(contents, indicator_transform)

                # retrieve the batch data from the transform
                data = transforms.batch
                if self._has_ti_data(data):
                    # use built-in method to write the data to
                    # disk, this method also updates heartbeat
                    self._write_batch_data(data, output_dir, 'domain')

    @staticmethod
    def _lazy_chunk(iterable, chunk_size=5_000):
        """Break iterable into chunks without consuming it first."""
        chunk = []
        for i in iterable:
            chunk.append(i)
            if len(chunk) >= chunk_size:
                yield chunk
                chunk = []

        yield chunk

    def _write_batch_data(self, data: 'Dict', output_dir: 'Path', type_: str):
        """Write results to a compressed file."""
        # update the task heartbeat
        self.update_heartbeat()

        total_data_length = len(data.get('group', [])) + len(data.get('indicator', []))

        if total_data_length < 5_000:
            self._write_results(data, output_dir, type_)
        else:
            if data.get('group', []):
                self._write_results({'group': data['group']}, output_dir, type_)
            if data.get('indicator', []):
                for chunk in self._lazy_chunk(data['indicator']):
                    self._write_results({'indicator': chunk}, output_dir, type_)

    @cached_property
    def task_settings(self) -> 'TaskSettingPipeModel':
        """Return the task settings.

        Tasks have standard model that is used to define the task settings. This method returns
        the settings model for the download task. Any additional settings can be defined in this
        property.

        The start and end date fields in the database are defined here and are automatically updated
        by the task manager when the task is started and completed.
        """

        return TaskSettingPipeModel(
            base_path=self.settings.base_path,
            date_field_start=JobRequestSchema.date_convert_start,
            date_field_complete=JobRequestSchema.date_convert_complete,
            description='Converts the CTI data into the ThreatConnect batch format.',
            max_execution_minutes=20,
            name='Convert',
        )
