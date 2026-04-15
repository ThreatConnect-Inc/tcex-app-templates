"""Notification Service - Sends TC notifications for pipeline health events."""

import logging
from datetime import timedelta
from functools import cached_property
from typing import NamedTuple

from tcex import TcEx
from tcex.api.tc.v3.tql.tql_operator import TqlOperator

logger = logging.getLogger('tcex')


DIGEST_INTERVAL_MAP: dict[str, timedelta] = {
    '1 Hour': timedelta(hours=1),
    '2 Hours': timedelta(hours=2),
    '3 Hours': timedelta(hours=3),
    '4 Hours': timedelta(hours=4),
}


class NotificationTypeConfig(NamedTuple):
    """Configuration for a single notification type."""

    category: str
    priority: str
    message_template: str | None


NOTIFICATION_TYPES: dict[str, NotificationTypeConfig] = {
    'App Startup': NotificationTypeConfig(
        category='app_startup',
        priority='Low',
        message_template='App starting',
    ),
    'App Startup Failed': NotificationTypeConfig(
        category='app_startup_failed',
        priority='High',
        message_template='App failed to start — {reason}',
    ),
    'App Shutdown': NotificationTypeConfig(
        category='app_shutdown',
        priority='High',
        message_template='App shutting down — {reason}',
    ),
    'Job Retrying': NotificationTypeConfig(
        category='job_retrying',
        priority='Medium',
        message_template='{count} job(s) failed and are retrying',
    ),
    'Job Failed': NotificationTypeConfig(
        category='job_failed',
        priority='High',
        message_template='{count} job(s) retried 10 times and failed'
        ' - job(s) stopped and will not be retried',
    ),
    'Job Recovered': NotificationTypeConfig(
        category='job_recovered',
        priority='Low',
        message_template='{count} failed job(s) have recovered and completed',
    ),
    'Manual': NotificationTypeConfig(
        category='manual',
        priority='Low',
        message_template=None,
    ),
}

# Reverse lookup: internal category → config
NOTIFICATION_BY_CATEGORY: dict[str, NotificationTypeConfig] = {
    v.category: v for v in NOTIFICATION_TYPES.values()
}


class NotificationService:
    """Sends TC notifications for pipeline health events."""

    def __init__(self, tcex: TcEx, owner_name: str, display_name_override: str | None = None):
        """Initialize with TcEx instance for API access."""
        self.tcex = tcex
        self._owner_name = owner_name
        self._owner_id: int | None = None
        self.log = logger
        self._display_name = display_name_override or str(tcex.app.ij.model.display_name)

    @property
    def owner_id(self) -> int:
        """Lazily resolve owner ID on first access."""
        if self._owner_id is None:
            self._owner_id = self._resolve_owner_id(self._owner_name)
        return self._owner_id

    @cached_property
    def notification_type(self) -> str:
        """Notification type label sent to TC, truncated to stay within API limits."""
        prefix = 'Service: '
        max_len = 100
        name = self._display_name

        if len(prefix) + len(name) > max_len:
            name = name[: max_len - len(prefix) - 3] + '...'

        return f'{prefix}{name}'

    @cached_property
    def msg_prefix(self) -> str:
        """Message prefix: 'App Name vX.Y.Z: '"""
        version = str(self.tcex.app.ij.model.program_version)
        return f'{self._display_name} v{version}: '

    def _resolve_owner_id(self, owner_name: str) -> int:
        """Resolve owner name to numeric owner ID via TC API."""
        owners = self.tcex.api.tc.v3.security.owners()
        owners.filter.owner_name(TqlOperator.EQ, owner_name)
        for owner in owners:
            if owner.model.id is not None:
                return owner.model.id
        raise RuntimeError(f'Cannot find owner {owner_name!r} in ThreatConnect instance.')

    def send(
        self,
        message: str,
        priority: str = 'Low',
    ) -> dict:
        """Send an org-wide notification via POST /v2/notifications.

        Calls the TC API directly to capture the full request and response
        for auditing. Always returns a dict — never raises.
        """
        request_body = {
            'notificationType': self.notification_type,
            'priority': priority,
            'isOrganization': False,
            'ownerId': self.owner_id,
            'message': message,
        }
        api_request = {
            'method': 'POST',
            'path': '/v2/notifications',
            'body': request_body,
        }

        try:
            r = self.tcex.session.tc.post('/v2/notifications', json=request_body)

            try:
                response_body = r.json()
            except Exception:
                response_body = r.text

            api_response = {'statusCode': r.status_code, 'body': response_body}

            if r.ok:
                return {
                    'send_status': 'success',
                    'status_code': r.status_code,
                    'status_text': r.reason,
                    'api_request': api_request,
                    'api_response': api_response,
                }
            return {
                'send_status': 'failed',
                'status_code': r.status_code,
                'status_text': r.text,
                'api_request': api_request,
                'api_response': api_response,
            }
        except Exception as ex:
            self.log.exception('notification-event=send-failed')
            return {
                'send_status': 'failed',
                'status_code': None,
                'status_text': str(ex),
                'api_request': api_request,
                'api_response': None,
            }
