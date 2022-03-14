"""App Inputs"""
# standard library
from typing import List, Optional

# third-party
from pydantic import BaseModel, validator
from tcex.input.field_types import Choice, DateTime, always_array, integer, string


class TCFiltersModel(BaseModel):
    """Standard inputs to filter indicators pulled from ThreatConnect."""

    tql: Optional[string(allow_empty=False)]
    indicator_types: List[Choice]
    owners: Optional[List[Choice]]
    tags: List[string(allow_empty=False)] = []
    max_false_positives: Optional[integer(gt=0)]
    minimum_confidence: Optional[integer(ge=0, le=100)]
    minimum_rating: Optional[integer(ge=1, le=5)]
    minimum_threatassess_score: Optional[integer(gt=0)]
    last_modified: DateTime

    _always_array = validator('tags', allow_reuse=True)(always_array(split_csv=True))


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
