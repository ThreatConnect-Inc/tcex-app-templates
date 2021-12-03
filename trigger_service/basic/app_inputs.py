"""App Inputs"""
# standard library
from typing import List, Optional, Union

# third-party
from pydantic import BaseModel, validator
from tcex.input.input import Input


class ServiceConfigModel(BaseModel):
    """Base model for the App containing any common inputs."""

    # playbookDataType = String, StringArray
    service_input: Union[List[str], str]


class TriggerConfigModel(BaseModel):
    playbook_input: str


class ServiceConfigInputs:
    """App Inputs"""

    def __init__(self, inputs: Input) -> None:
        """Initialize class properties."""
        self.inputs = inputs
        self.update_inputs()

    def update_inputs(self) -> None:
        """Add custom App models to inputs. Validation will run at the same time."""
        self.inputs.add_model(ServiceConfigModel)
