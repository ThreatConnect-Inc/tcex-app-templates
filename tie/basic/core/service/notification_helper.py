"""Notification helper for sending custom notifications from task code."""

import logging
from functools import cached_property

from tcex import TcEx

from core.json_db import JsonDB
from core.model.settings_model_base import SettingModelBase
from core.model.tie.notification_model import NotificationModel
from core.service.notification_service import (
    NOTIFICATION_TYPES,
    NotificationService,
    NotificationTypeConfig,
)

logger = logging.getLogger('tcex')


class NotificationHelper:
    """Send notifications from task code or the Tasks orchestrator.

    Accepts either a string label (looked up in NOTIFICATION_TYPES) or a
    NotificationTypeConfig directly. Task code uses string labels; the Tasks
    orchestrator passes configs directly since it already has them.

    Custom types must be registered in NOTIFICATION_TYPES before use (typically
    in app_inputs.py). Once registered, they integrate automatically with the
    parse_notification_types validator and settings.app_settings.notification_types opt-in.

    Examples:
        >>> # Register a custom type in app_inputs.py:
        >>> NOTIFICATION_TYPES['Alert Source Errors'] = (
        ...     NotificationTypeConfig(
        ...         category='alert_source_errors',
        ...         priority='Medium',
        ...         message_template='{count} source(s) failed to download',
        ...     )
        ... )

        >>> # Use in a task (add as a cached_property for fork safety):
        >>> helper.notify('Alert Source Errors', send_now=True, count=3)
        >>> helper.notify(
        ...     'Alert Source Errors',
        ...     message='custom message',
        ...     send_now=False,
        ... )
    """

    def __init__(self, settings: SettingModelBase, tcex: TcEx, db: JsonDB):
        """Initialize class properties."""
        self._settings = settings
        self._tcex = tcex
        self._db = db
        self.log = logger

    @cached_property
    def _notification_service(self) -> NotificationService:
        """Lazily create NotificationService — deferred for fork safety in task code."""
        return NotificationService(
            self._tcex,
            owner_name=self._settings.tc_owner,
            display_name_override=self._settings.notification_display_name,
        )

    def notify(
        self,
        notification_type: str | NotificationTypeConfig,
        message: str | None = None,
        send_now: bool = True,
        job_ids: list[str] | None = None,
        **format_kwargs,
    ) -> None:
        """Send or store a notification.

        Pass a string label to look up the type in NOTIFICATION_TYPES (developer
        task code path). Pass a NotificationTypeConfig directly to skip the lookup
        (Tasks orchestrator path — caller is responsible for the notifications_enabled
        gate).

        For string labels: does nothing if notifications are globally disabled
        (notification_digest_interval is None).

        If the type config has a message_template, it is formatted with any
        format_kwargs. Pass message= to override the template or when
        message_template is None.

        send_now=True sends immediately via the TC API (if the category is in
        settings.app_settings.notification_types) and stores in the DB.
        send_now=False stores in the DB only — visible in the Notifications UI.
        """
        if isinstance(notification_type, str):
            if self._settings.app_settings.notification_digest_interval is None:
                self.log.debug(
                    f'action=notify, type={notification_type!r}, '
                    f'status=skipped, reason=notifications_disabled'
                )
                return
            notification_config = NOTIFICATION_TYPES[notification_type]
            notification_types = self._settings.app_settings.notification_types or []
            should_send = send_now and notification_config.category in notification_types
        else:
            notification_config = notification_type
            should_send = send_now

        if notification_config.message_template is not None:
            message_body = notification_config.message_template.format(**format_kwargs)
        elif message is not None:
            message_body = message
        else:
            raise ValueError(
                f'notification type {notification_config.category!r} has no message_template; '
                f'pass message= or add a message_template to the type config'
            )

        prefixed_message = f'{self._notification_service.msg_prefix}{message_body}'

        self.log.info(
            f'action=notify, category={notification_config.category}, '
            f'send_now={send_now}, should_send={should_send}'
        )

        api_request = None
        api_response = None
        send_status = None
        status_code = None
        status_text = None

        if should_send:
            result = self._notification_service.send(prefixed_message, notification_config.priority)
            send_status = result['send_status']
            status_code = result['status_code']
            status_text = result['status_text']
            api_request = result['api_request']
            api_response = result['api_response']
            self.log.info(
                f'action=notify, category={notification_config.category}, '
                f'send_status={send_status}, status_code={status_code}'
            )

        notification = NotificationModel(
            notification_type=self._notification_service.notification_type,
            category=notification_config.category,
            priority=notification_config.priority,
            message=prefixed_message,
            job_ids=job_ids or [],
            send_status=send_status,
            send_status_code=status_code,
            send_status_text=status_text,
            api_request=api_request,
            api_response=api_response,
        )
        self._db.save(notification)
