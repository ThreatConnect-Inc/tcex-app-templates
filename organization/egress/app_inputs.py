"""App Inputs"""
# standard library
from typing import List, Optional

# third-party
from pydantic import BaseModel, validator
from pydantic.class_validators import root_validator
from tcex.input.field_types import Choice, DateTime, always_array, integer, string


def validate_tql(cls, values: dict):  # pylint: disable=unused-argument
    """Validate tql vs other fields that are required"""

    # validate that if tql is empty, then
    # 1. last_modified is required
    # 2. indicator_types is required
    # 3. owners is required
    if not values.get('tql', None):
        if not values.get('last_modified', None):
            raise ValueError('last_modified must not be empty')
        if not values.get('indicator_types', None):
            raise ValueError('indicator_types must have 1 type selected')
        if not values.get('owners', None):
            raise ValueError('owners must have at least 1 selected')
    return values


class TCFiltersModel(BaseModel):
    """Standard inputs to filter indicators pulled from ThreatConnect."""

    tql: Optional[string(allow_empty=False)]
    indicator_types: List[Choice]
    owners: Optional[List[Choice]]
    max_false_positives: Optional[integer(gt=0)]
    minimum_confidence: Optional[integer(ge=0, le=100)]
    minimum_rating: Optional[integer(ge=1, le=5)]
    minimum_threatassess_score: Optional[integer(gt=0, le=1_000)]
    last_modified: DateTime

    # validates what we get from core and then turns to array
    tags: Optional[string(allow_empty=False)]
    _always_array = validator('tags', allow_reuse=True)(always_array(split_csv=True))

    # validate that if tql is empty, then
    # 1. last_modified is required
    # 2. indicator_type is required
    # 3. owners is required
    _tql_none_validation = root_validator(allow_reuse=True)(validate_tql)


class AppBaseModel(TCFiltersModel):
    """Base model for the App containing any common inputs."""


class AppInputs:
    """App Inputs"""

    def __init__(self, inputs: BaseModel) -> None:
        """Initialize class properties."""
        self.inputs = inputs

    def update_inputs(self) -> None:
        """Add custom App models to inputs. Validation will run at the same time."""
        self.inputs.add_model(AppBaseModel)
