"""Model Definition"""
# third-party
from pydantic import BaseModel, Extra, Field, validator


class TaskSettingModel(BaseModel):
    """Model Definition"""

    # the task description
    description: str = Field('A generic task', description='The task description.')

    max_execution_minutes: int = Field(
        60, description='Max execution time before a task is killed.'
    )

    # the name value is used when creating task working directories and for DB status values
    name: str = Field(..., description='The name of the task.')

    # task controls
    paused: bool = Field(False, description='Indicates if the task is paused.')
    paused_file: bool = Field(False, description='Indicates if the task is paused by a PAUSE file.')
    paused_file_global: bool = Field(
        False, description='Indicates if the task is paused by a global PAUSE file.'
    )

    # override default schedule settings (how often tasks run)
    schedule_period: int = Field(5, description='The numerical unit for the schedule.')
    schedule_unit: str = Field(
        'seconds', description='The unit for the schedule (e.g., seconds, hours, days).'
    )

    # slug easy to type name
    slug: str = Field('slug', description='The slug of the task.')

    # the type of task (e.g., path_pipe, standalone)
    task_type: str = Field('standalone', description='The type of task (e.g., pipe, single).')

    # pylint: disable=no-self-argument
    @validator('slug', always=True, pre=True)
    def _create_slug(cls, _, values):
        return values.get('name').lower().replace(' ', '-')

    class Config:
        """Model Definition"""

        extra = Extra.allow
