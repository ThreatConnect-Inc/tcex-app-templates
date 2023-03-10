"""Database Field Type Definition"""
# standard library
import logging
from datetime import timezone

# third-party
import arrow
from sqlalchemy import types

# logger
logger = logging.getLogger('tcex')


# pylint: disable=abstract-method
class ArrowDateTime(types.TypeDecorator):
    """Database Field Type Definition"""

    cache_ok = True
    impl = types.DateTime

    def process_bind_param(self, value, _):
        """Modify the value before being written.

        Using arrow.utcnow() to ensure the value is UTC, but sqlite requires a datetime.
        """
        if hasattr(value, 'tzinfo') and value.tzinfo is None:
            logger.error(f'feature=arrow-date-time, value={value}, error=received-naive-datetime')

        # sqlite requires a datetime type, convert any arrow types to datetime
        if hasattr(value, 'datetime'):
            value = value.datetime
        return value

    def process_result_value(self, value, _):
        """Modify the value before being returned.

        Values are UTC when added, but sqlite does not store timezone information. Ensure
        the value is not a naive datetime when returned.
        """
        if hasattr(value, 'tzinfo') and value.tzinfo is None:
            value = arrow.get(value).replace(tzinfo=timezone.utc)
        return value
