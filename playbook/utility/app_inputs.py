"""App Inputs"""

# third-party
from tcex.input.field_type import KeyValue, TCEntity
from tcex.input.input import Input
from tcex.input.model.app_playbook_model import AppPlaybookModel


class AppBaseModel(AppPlaybookModel):
    """Base model for the App containing any common inputs."""

    indent: int = 4
    # install.json defines the following playbook data types:
    # KeyValue      - KeyValueModel
    # KeyValueArray - List[KeyValueModel]
    # String        - str
    # StringArray   - List[str]
    # TCEntity      - TCEntityModel
    # TCEntityArray - List[TCEntityModel]
    json_data: KeyValue | list[KeyValue] | str | list[str] | TCEntity | list[TCEntity]
    sort_keys: bool = False


class AppInputs:
    """App Inputs"""

    def __init__(self, inputs: Input) -> None:
        """Initialize class properties."""
        self.inputs = inputs

    def update_inputs(self) -> None:
        """Add custom App models to inputs. Validation will run at the same time."""
        self.inputs.add_model(AppBaseModel)
