"""Notification DAO."""

import contextlib

from core.api.validation.models.query_param_filter_pagination_model import (
    QueryParamFilterPaginationModel,
)
from core.json_db import JsonDB
from core.json_db.dao import JsonDBDAO
from core.json_db.json_db import SortBy, SortOrder
from core.model.tie.notification_model import NotificationModel


class NotificationDAO(JsonDBDAO[NotificationModel]):
    """Notification DAO"""

    def __init__(self, db: JsonDB):
        """."""
        super().__init__(db, NotificationModel)

    def get_by_id(self, notification_id: str) -> NotificationModel | None:
        """Get a single notification by ID."""
        try:
            return self.db.load(NotificationModel, notification_id)
        except FileNotFoundError:
            return None

    def get_page_for_query_params(self, query_params: QueryParamFilterPaginationModel) -> dict:
        """Get a page of notifications with optional filtering."""
        sort_by = query_params.sort

        if isinstance(sort_by, str):
            with contextlib.suppress(KeyError):
                sort_by = SortBy[sort_by.upper()]

        paths = self.db.get_paths(
            NotificationModel,
            sort_by=sort_by if isinstance(sort_by, SortBy) else SortBy.INDEX,
            sort_order=query_params.sort_order,
        )

        notifications = self.db.load_paths(NotificationModel, paths)

        if not isinstance(sort_by, SortBy):
            notifications.sort(
                key=lambda x: getattr(x, sort_by),
                reverse=query_params.sort_order == SortOrder.DESC,
            )

        # Apply filters
        notifications = self._apply_filters(notifications, query_params)

        page_data = (
            notifications[query_params.offset : query_params.offset + query_params.limit]
            if query_params.limit
            else notifications[query_params.offset :]
        )

        return {
            'totalCount': len(notifications),
            'count': len(page_data),
            'data': page_data,
        }

    @staticmethod
    def _apply_filters(
        notifications: list[NotificationModel],
        query_params: QueryParamFilterPaginationModel,
    ) -> list[NotificationModel]:
        """Apply optional filters from query params."""
        category = getattr(query_params, 'category', None)
        if category:
            allowed = {c.strip() for c in category.split(',')}
            notifications = [n for n in notifications if n.category in allowed]

        priority = getattr(query_params, 'priority', None)
        if priority:
            allowed = {p.strip() for p in priority.split(',')}
            notifications = [n for n in notifications if n.priority in allowed]

        send_status = getattr(query_params, 'send_status', None)
        if send_status is not None:
            # Convert comma-separated values to a set
            # Valid values: "success", "failed", "not_sent" (maps to None on the model)
            allowed = {s.strip().lower() for s in send_status.split(',')}
            notifications = [n for n in notifications if (n.send_status or 'not_sent') in allowed]

        return notifications
