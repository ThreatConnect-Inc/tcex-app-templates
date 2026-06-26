"""Class for /api/notification endpoint"""

import json as json_lib
import logging
from functools import cached_property

import falcon
from pydantic import Field, validator
from spectree import Response

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_notification
from core.api.validation.models.query_param_filter_pagination_model import (
    QueryParamFilterPaginationModel,
)
from core.dao.notification_dao import NotificationDAO
from core.json_db import SortBy
from core.model.model_base import ModelBase
from core.model.tie.notification_model import (
    NotificationModel,
    NotificationPaginatedResponseModel,
)
from core.service.notification_service import NotificationService

logger = logging.getLogger('tcex')


class GetQueryParamModel(QueryParamFilterPaginationModel):
    """Query params for GET /api/notification"""

    category: str | None = Field(None, description='Filter by category (comma-separated)')
    priority: str | None = Field(None, description='Filter by priority (comma-separated)')
    send_status: str | None = Field(
        None, description='Filter by send status (comma-separated: success,failed,not_sent)'
    )

    @validator('sort', always=True, pre=True)
    def _sort(cls, v):
        """Validate sort value."""
        match v.lower():
            case 'id' | 'index':
                return SortBy.INDEX
            case 'created':
                return SortBy.INDEX
            case 'modified':
                return SortBy.MODIFIED
            case _:
                return v


class PostBodyModel(ModelBase):
    """Body model for POST /api/notification"""

    message: str = Field(...)
    priority: str = Field(default='Medium')


class NotificationCollection(EndpointBase):
    """Class for /api/notification endpoint"""

    @cached_property
    def dao(self) -> NotificationDAO:
        """Return a new instance of the DAO."""
        return NotificationDAO(self.db)

    @cached_property
    def notification_service(self) -> NotificationService:
        """Return a new instance of the NotificationService."""
        return NotificationService(
            self.tcex,
            owner_name=self.settings.tc_owner,
            display_name_override=self.settings.notification_display_name,
        )

    @spec.validate(
        query=GetQueryParamModel,
        resp=Response(HTTP_200=NotificationPaginatedResponseModel),
        skip_validation=True,
        tags=[tag_notification],
    )
    def on_get(
        self,
        req: FalconRequest,  # noqa: ARG002
        resp: FalconResponse,
        query_params: GetQueryParamModel,
    ):
        """Return paginated notifications."""
        resp_data = self.dao.get_page_for_query_params(query_params)
        resp.media = resp.response_model(
            resp_data, NotificationPaginatedResponseModel, query_params
        )

    @spec.validate(
        resp=Response('HTTP_201'),
        skip_validation=True,
        tags=[tag_notification],
    )
    def on_post(
        self,
        req: FalconRequest,
        resp: FalconResponse,
    ):
        """Send a notification and store it.

        Always stores the notification regardless of whether the TC API send succeeds.
        The send_status field records the outcome.
        """
        body = req.media or {}
        try:
            parsed = PostBodyModel(**body)
        except Exception as ex:
            raise falcon.HTTPBadRequest(title='Bad Request', description=str(ex)) from ex

        prefixed_message = f'{self.notification_service.msg_prefix}{parsed.message}'
        result = self.notification_service.send(prefixed_message, parsed.priority)

        notification = NotificationModel(
            category='manual',
            notification_type=self.notification_service.notification_type,
            priority=parsed.priority,
            message=prefixed_message,
            send_status=result['send_status'],
            send_status_code=result['status_code'],
            send_status_text=result['status_text'],
            api_request=result['api_request'],
            api_response=result['api_response'],
        )
        self.db.save(notification)
        resp.media = json_lib.loads(notification.json(by_alias=True))
        resp.status = '201 Created'
