"""App Inputs"""
# standard library
from typing import List, Union

# third-party
from pydantic import BaseModel
from tcex.input.models import KeyValueModel, TCEntityModel


class AppBaseModel(BaseModel):
    """Base model for the App containing any common inputs."""

    indent: int = 4
    # install.json defines the following playbook data types:
    # KeyValue      - KeyValueModel
    # KeyValueArray - List[KeyValueModel]
    # String        - str
    # StringArray   - List[str]
    # TCEntity      - TCEntityModel
    # TCEntityArray - List[TCEntityModel]
    json_data: Union[
        KeyValueModel, List[KeyValueModel], str, List[str], TCEntityModel, List[TCEntityModel]
    ]
    sort_keys: bool = False


class AppInputs:
    """App Inputs"""

    def __init__(self, inputs: BaseModel) -> None:
        """Initialize class properties."""
        self.inputs = inputs

        # update with custom models and run validation
        self.update_inputs()

    def update_inputs(self) -> None:
        """Add custom App models to inputs. Validation will run at the same time."""
        self.inputs.add_model(AppBaseModel)
