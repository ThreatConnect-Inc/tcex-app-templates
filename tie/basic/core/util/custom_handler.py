"""DatetimeEncoder class."""

# standard library
import json
from datetime import date, datetime, timedelta

# third-party
import arrow


class CustomHandler(json.JSONEncoder):
    """Json Encoder that supports datetime objects."""

    def default(self, o):  # type: ignore
        """Implement custom JSON Encoder."""
        handlers = {
            arrow.Arrow: lambda x: x.isoformat(),
            date: lambda x: x.isoformat(),
            datetime: lambda x: x.isoformat(),
            timedelta: lambda x: x.total_seconds(),
            set: lambda x: list(x),  # pylint: disable=unnecessary-lambda
        }
        handler = handlers.get(type(o), super().default)
        return handler(o)
