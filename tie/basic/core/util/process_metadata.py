"""Process Metadata"""

import logging
import multiprocessing
import platform
import time
from datetime import UTC

import setproctitle

import arrow
from pydantic import BaseModel, ConfigDict, model_validator

logger = logging.getLogger('tcex')

if not platform.platform().upper().startswith('LINUX'):
    logger.warning(
        f'Running on an unsupported OS: {platform.platform()}.  '
        'Will set spawn method to fork, but this may not work!'
    )
    multiprocessing.set_start_method('fork')


class Metadata(BaseModel):
    """Metadata common to all ProcessMetadata instances.

    Note this model allows extra, so arbitrary values can be attached to metadata.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra='allow')

    max_execution_time_minutes: int
    last_heartbeat: arrow.Arrow
    expires_percent: int | None
    is_alive: bool
    is_daemon: bool
    name: str
    pid: int

    @model_validator(mode='before')
    @classmethod
    def expires_percent(cls, values):
        """Calculate percent of max runtime that has elapsed."""
        last_heartbeat: arrow.Arrow = values.get('last_heartbeat')
        date_expires: arrow.Arrow = last_heartbeat.shift(
            minutes=values['max_execution_time_minutes']
        )
        time_diff = date_expires - last_heartbeat
        if time_diff.total_seconds() <= 0:
            # Zero or negative time diff means already expired or invalid config
            expires_percent = 100
        else:
            expires_percent = int(
                ((arrow.now(UTC) - last_heartbeat) / (date_expires - last_heartbeat)) * 100
            )
            # Clamp to 0-100 range (can exceed 100 if past deadline, or be negative with clock skew)
            expires_percent = max(0, min(100, expires_percent))

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
            group=group,
            target=target,
            name=name,
            args=args,
            kwargs=kwargs,
            daemon=daemon,
        )
        self.ns = ns
        self._metadata = metadata

    def run(self):
        """Set the OS-level process title before running the target."""
        # setproctitle.setproctitle(f'tie-task: {self.name}')

        args = ' '.join(
            [
                f'--tie.task={self.name.lower().replace(" ", "-")}',
                f'--tie.started={int(time.time())}',
            ]
        )
        setproctitle.setproctitle(f'{setproctitle.getproctitle()} {args}')
        super().run()

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
