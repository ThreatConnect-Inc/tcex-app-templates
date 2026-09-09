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
    description: str | None = None


NOTIFICATION_TYPES: dict[str, NotificationTypeConfig] = {
    'App Startup': NotificationTypeConfig(
        category='app_startup',
        priority='Low',
        message_template='App starting',
        description=(
            'Sent every time the app starts, including after a ThreatConnect restart or a '
            'redeploy. Useful as a heartbeat for confirming a deployment landed; noisy if '
            'the server restarts on a schedule.'
        ),
    ),
    'App Startup Failed': NotificationTypeConfig(
        category='app_startup_failed',
        priority='High',
        message_template='App failed to start — {reason}',
        description=(
            'The app could not start — usually bad credentials, an unreachable vendor API, '
            'or a failed preflight check. Nothing will be ingested until it is fixed, so '
            'this is the one type worth keeping on even in a quiet environment.'
        ),
    ),
    'App Shutdown': NotificationTypeConfig(
        category='app_shutdown',
        priority='High',
        message_template='App shutting down — {reason}',
        description=(
            'The app is stopping, with the reason it was given. Expected during a redeploy '
            'or a server restart; unexpected otherwise, and paired with a missing App '
            'Startup it tells you ingestion has stopped rather than paused.'
        ),
    ),
    'Setup Required': NotificationTypeConfig(
        category='setup_required',
        priority='High',
        message_template=(
            'Setup is incomplete — no ingestion will run until it is finished. '
            '<a href="{link}">Click here to finish setup</a>'
        ),
        description=(
            'Setup has never been completed, so no ingestion is running at all. Sent when '
            'the app starts and then on the notification digest interval until setup is '
            'finished, and stops on its own once it is. Includes a direct link to the '
            'Settings page when one is available; until then it tells you where to go.'
        ),
    ),
    'Job Retrying': NotificationTypeConfig(
        category='job_retrying',
        priority='Medium',
        message_template='{count} job(s) failed and are retrying',
        description=(
            'One or more jobs failed and are being retried automatically. Usually a '
            'transient vendor error that resolves itself, so this is the type to turn off '
            'first if the notification center is too busy — a job that never recovers '
            'raises Job Failed anyway.'
        ),
    ),
    'Job Failed': NotificationTypeConfig(
        category='job_failed',
        priority='High',
        message_template='{count} job(s) retried 10 times and failed'
        ' - job(s) stopped and will not be retried',
        description=(
            'A job exhausted all ten retries and has stopped for good. Nothing further is '
            'automatic — the data for that window will be missing until someone looks at '
            'the job and reruns it.'
        ),
    ),
    'Job Recovered': NotificationTypeConfig(
        category='job_recovered',
        priority='Low',
        message_template='{count} failed job(s) have recovered and completed',
        description=(
            'A job that had been failing has now completed. The counterpart to Job '
            'Retrying: keep both on to see a problem close, or neither to hear only about '
            'jobs that gave up.'
        ),
    ),
    'Manual': NotificationTypeConfig(
        category='manual',
        priority='Low',
        message_template=None,
        description=(
            'Messages raised deliberately by app code rather than by the pipeline itself, '
            'for anything an integration decides is worth telling an operator about. What '
            'these say is entirely up to the app.'
        ),
    ),
}

# Reverse lookup: internal category → config
NOTIFICATION_BY_CATEGORY: dict[str, NotificationTypeConfig] = {
    v.category: v for v in NOTIFICATION_TYPES.values()
}


class NotificationService:
    """Sends TC notifications for pipeline health events."""

    def __init__(
        self,
        tcex: TcEx,
        owner_name: str | None = None,
        display_name_override: str | None = None,
    ):
        """Initialize with TcEx instance for API access."""
        self.tcex = tcex
        self._owner_name = owner_name
        self._owner_id: int | None = None
        self.log = logger
        self._display_name = display_name_override or str(tcex.app.ij.model.display_name)

    @property
    def is_organization(self) -> bool:
        """True when no owner name is configured — send org-wide instead of owner-scoped."""
        return not self._owner_name

    @property
    def owner_id(self) -> int | None:
        """Lazily resolve owner ID on first access.

        Returns None when no owner name is configured, since org-wide
        notifications don't require an owner ID.
        """
        if not self._owner_name:
            return None
        if self._owner_id is None:
            self._owner_id = self._resolve_owner_id(self._owner_name)
        return self._owner_id

    @cached_property
    def notification_type(self) -> str:
        """Notification type label sent to TC."""
        return 'App Notification'

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
            'isOrganization': self.is_organization,
            'message': message,
        }
        if not self.is_organization:
            request_body['ownerId'] = self.owner_id
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
