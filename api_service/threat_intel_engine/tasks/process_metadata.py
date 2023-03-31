"""Process Metadata"""
# standard library
import logging
import multiprocessing
import platform

# third-party
import arrow
from pydantic import BaseModel, Extra, root_validator

logger = logging.getLogger('tcex')

if not platform.platform().upper().startswith('LINUX'):
    logger.warning(
        f'Running on an unsupported OS: {platform.platform()}.  '
        'Will set spawn method to fork, but this may not work!'
    )
    multiprocessing.set_start_method('fork')


class Metadata(BaseModel, arbitrary_types_allowed=True, extra=Extra.allow):
    """Metadata common to all ProcessMetadata instances.

    Note this model allows extra, so arbitrary values can be attached to metadata.
    """

    max_execution_time_minutes: int
    last_heartbeat: arrow.Arrow
    expires_percent: int | None
    is_alive: bool
    is_daemon: bool
    name: str
    pid: int

    @root_validator
    def expires_percent(cls, values):  # pylint: disable=no-self-argument
        """Calculate percent of max runtime that has elapsed."""
        last_heartbeat: 'arrow.Arrow' = values.get('last_heartbeat')
        date_expires: 'arrow.Arrow' = last_heartbeat.shift(
            minutes=values['max_execution_time_minutes']
        )
        expires_percent = int(
            ((arrow.utcnow() - last_heartbeat) / (date_expires - last_heartbeat)) * 100
        )

        values['expires_percent'] = expires_percent

        return values


class ProcessMetadata(multiprocessing.Process):
    """Wrapper around Process to attach metadata."""

    def __init__(
        self,
        group=None,
        target=None,
        name=None,
        args=(),
        kwargs=None,
        *,
        daemon=None,
        ns=None,
        **metadata,
    ):
        """Init"""
        kwargs = {} if kwargs is None else kwargs
        super().__init__(
            group=group, target=target, name=name, args=args, kwargs=kwargs, daemon=daemon
        )
        self.ns = ns
        self._metadata = metadata

    @property
    def metadata(self):
        """Return metadata."""
        self._metadata.update(
            {
                'name': self.name,
                'pid': self.pid,
                'is_alive': self.is_alive(),
                'is_daemon': self.daemon,
                'last_heartbeat': self.ns.heartbeat,
            }
        )
        return Metadata(**self._metadata)
