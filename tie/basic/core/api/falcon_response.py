"""Falcon Response Class"""

from __future__ import annotations

from typing import Any

import falcon
from pydantic import BaseModel, ValidationError

from core.api.validation.models.query_param_filter_model import QueryParamFilterModel
from core.api.validation.models.query_param_filter_pagination_model import (
    QueryParamFilterPaginationModel,
)
from core.api.validation.models.query_param_model import QueryParamModel


class FalconResponse(falcon.Response):
    """New Falcon Response class."""

    def response_model(
        self,
        response_data: BaseModel | dict | list[dict],
        model: type[BaseModel],
        params: QueryParamModel | QueryParamFilterModel | QueryParamFilterPaginationModel,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Apply field filters and return response text."""
        media: dict | list[dict]
        try:
            if isinstance(response_data, type(BaseModel)):
                media = response_data.model_dump(**params.filter_values)
            elif isinstance(response_data, list):
                media = [
                    model.model_validate(a).model_dump(**params.filter_values)
                    for a in response_data
                ]
            else:
                media = model.model_validate(response_data).model_dump(**params.filter_values)
        except ValidationError as ex:
            raise falcon.HTTPInternalServerError from ex
        except Exception as ex:
            raise falcon.HTTPInternalServerError from ex
        return media
