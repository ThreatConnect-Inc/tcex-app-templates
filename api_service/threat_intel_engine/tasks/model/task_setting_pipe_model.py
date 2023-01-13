"""Model Definition"""
# standard library
import re
from pathlib import Path
from typing import Optional

# third-party
from pydantic import Field, validator
from sqlalchemy.orm.attributes import InstrumentedAttribute

from .task_setting_model import TaskSettingModel


# pylint: disable=no-self-argument,no-self-use
class TaskSettingPipeModel(TaskSettingModel):
    """Model Definition"""

    # we pull this from the settings model, if we do this with more
    # than 3 things, we should just pull in the entire settings model.
    base_path: Path = Field(..., description='Base path where all the working directories will be.')

    # define db field names that need to be updated
    date_field_start: str = Field(
        ..., description='The DB field used to store the task start time.'
    )
    date_field_complete: str = Field(
        ..., description='The DB field used to store the task complete time.'
    )

    # this index or order of the tasks in the pipe
    index: Optional[int] = Field(None, description='The index of the task in the pipe.')

    # pipe setting
    pipe_task_complete: bool = Field(
        False, description='Indicates if the task is the last task in the pipe.'
    )
    pipe_task_start: bool = Field(
        False, description='Indicators if the task is the first task in the pipe.'
    )

    # used to create input directory
    previous_task_name: Optional[str] = Field(None, description='The name of the previous task.')

    # the type of task (e.g., path_pipe, standalone)
    task_type: str = Field('path_pipe', description='The type of task (e.g., pipe, single).')

    # set the working directory for the task
    working_dir_out: Optional[Path] = Field(
        None, description='The output working directory for the task. Set by tasks.add_task_pipe.'
    )

    @validator('date_field_start', 'date_field_complete', always=True, pre=True)
    def _column_fields(cls, v):
        """Validate that the column field is a Column object."""
        if isinstance(v, InstrumentedAttribute):
            v = v.name
        return v

    class Config:
        """Model Configuration"""

        validate_assignment = True

    def camel_to_snake(self, camel_string: str) -> str:
        """Return snake case string from a camel case string."""
        camel_pattern = re.compile(r'(?<!^)(?=[A-Z])')
        return camel_pattern.sub('_', camel_string).lower()

    @property
    def failed_working_dir(self) -> Path:
        """Return the path to the failed file."""
        _failed_working_dir = self.base_path / 'failed_working_dir'
        _failed_working_dir.mkdir(parents=True, exist_ok=True)
        return _failed_working_dir

    @property
    def name_camel(self) -> str:
        """Return name in camel case."""
        return self.camel_to_snake(self.name)

    @property
    def previous_task_name_camel(self) -> str:
        """Return name in camel case."""
        if self.previous_task_name is not None:
            return self.camel_to_snake(self.previous_task_name)
        raise RuntimeError(f'{self.name} previous_task_name is not set.')

    @property
    def status_active(self) -> str:
        """Return the active status for the task."""
        return f'{self.name.lower()} in progress'  # pylint: disable=no-member

    @property
    def status_complete(self) -> str:
        """Return the complete status for the task."""
        return f'{self.name.lower()} complete'  # pylint: disable=no-member

    @property
    def working_dir_in(self) -> Path:
        """Return the working directory for the task."""
        directory_name = f'{self.name_camel}_working_dir'
        _path = self.base_path / directory_name
        _path.mkdir(parents=True, exist_ok=True)
        return _path
