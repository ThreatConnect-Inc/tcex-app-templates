"""Validate feature test case class."""
# first-party
from tests.validate_custom import ValidateCustom


class ValidateFeature(ValidateCustom):
    """Validate for Feature lowercase

    This file will only be auto-generated once to ensure any changes are not overwritten.
    """

    def __init__(self, validator: object):  # pylint: disable=useless-super-delegation
        """Initialize class properties."""
        super().__init__(validator)
