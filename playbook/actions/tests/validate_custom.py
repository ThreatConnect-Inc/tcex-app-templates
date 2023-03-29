"""Validate custom test case class."""
# third-party
from tests.validate import Validate


class ValidateCustom(Validate):
    """Validate for Feature capitalize

    This file will only be auto-generated once to ensure any changes are not overwritten.
    """

    def __init__(self, validator: object):  # pylint: disable=useless-super-delegation
        """Initialize class properties."""
        super().__init__(validator)
