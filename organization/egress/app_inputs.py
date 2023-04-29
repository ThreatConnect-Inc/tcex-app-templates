"""App Inputs"""
# pyright: reportGeneralTypeIssues=false

# third-party
from pydantic import validator
from pydantic.class_validators import root_validator
from tcex.input.field_type import Choice, DateTime, always_array, integer, string
from tcex.input.input import Input
from tcex.input.model.app_organization_model import AppOrganizationModel


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
    else:
        # TQL has a value.
        # Verify that none of the filters (except owners) have values as they are ignored.
        # Was decided so we have feedback to the user rather then silently
        # having fields they picked ignored.
        #
        # If they have selected owners, then check there is no ownerName within the TQL string.
        if any(
            [
                values.get('indicator_types', None),
                values.get('max_false_positives', None),
                values.get('minimum_confidence', None),
                values.get('minimum_rating', None),
                values.get('minimum_threatassess_score', None),
                values.get('last_modified', None),
                values.get('tags', None),
            ]
        ):
            raise ValueError(
                'TQL is not allowed when other filters are selected except for owners.'
            )

        if values.get('owners', None) and 'ownerName' in values.get('tql', ''):
            # They have selected an owner, check if the TQL contains ownerName
            raise ValueError(
                'There is an owner selected, but the TQL contains ownerName. This is not allowed.'
            )
    return values


class TCFiltersModel(AppOrganizationModel):
    """Standard inputs to filter indicators pulled from ThreatConnect."""

    tql: string(allow_empty=False) | None
    indicator_types: list[Choice] | None
    owners: list[Choice] | None
    max_false_positives: integer(gt=0) | None
    minimum_confidence: integer(ge=0, le=100) | None
    minimum_rating: integer(ge=1, le=5) | None
    minimum_threatassess_score: integer(gt=0, le=1_000) | None
    last_modified: DateTime | None

    # validates what we get from core and then turns to array
    tags: string(allow_empty=False) | None
    _always_array = validator('tags', allow_reuse=True)(always_array(split_csv=True))

    # validate that if tql is empty, then
    # 1. last_modified is required
    # 2. indicator_type is required
    # 3. owners is required
    # validate if tql is not empty, then
    # 1. no other filters are allowed (except owners)
    # validate if tql is not empty and contains ownerName, then
    # 1. no owner is selected
    _tql_none_validation = root_validator(allow_reuse=True)(validate_tql)


class AppBaseModel(TCFiltersModel):
    """Base model for the App containing any common inputs."""


class AppInputs:
    """App Inputs."""

    def __init__(self, inputs: Input) -> None:
        """Initialize class properties."""
        self.inputs = inputs

    def update_inputs(self) -> None:
        """Add custom App models to inputs. Validation will run at the same time."""
        self.inputs.add_model(AppBaseModel)
