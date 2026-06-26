"""Falcon Validation hook module."""

from __future__ import annotations

import json
import logging
import traceback
from typing import Generic, TypeVar

import falcon
from pydantic import BaseModel, ValidationError, parse_obj_as

from core.api.error.util import error
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.model_base import ModelBase

# from core.api.validation.models import (
#     QueryParamFilterModel,
#     QueryParamFilterPaginationModel,
# )

# get primary API logger
logger = logging.getLogger('tcex')

T = TypeVar('T', bound=BaseModel)


class PaginatorResponseModel(ModelBase):
    """Pagination model for collection responses."""

    count: int | None = None
    data: list[dict]
    next: str | None = None
    previous: str | None = None
    total_count: int | None = None


class PaginatorResponseBodyModel(PaginatorResponseModel, Generic[T]):
    """Pagination model for collection responses."""

    data: list[T]


def _process_validation_request_errors(ex: ValidationError, req: FalconRequest):
    """Process any validation errors."""
    errors = json.loads(ex.json())
    for e in errors:
        e['field'] = e.pop('loc')  # rename loc to field for clarity

    err = error(
        description=errors,
        req=req,
        title='Bad Request',
    )
    raise falcon.HTTPBadRequest(**err) from ex


def _process_validation_response_errors(ex: ValidationError, req: FalconRequest):
    """Process any validation errors."""
    errors = json.loads(ex.json())
    for e in errors:
        e['field'] = e.pop('loc')  # rename loc to field for clarity
        e.pop('url', None)  # remove url from error response

    err = error(
        description=errors,
        req=req,
        title='Internal Server Error',
    )
    raise falcon.HTTPInternalServerError(**err) from ex


def format_validation_errors(
    ex: ValidationError, title: str, req: FalconRequest | None = None
) -> dict:
    """Process any validation errors."""
    errors = json.loads(ex.json())
    for e in errors:
        e['field'] = e.pop('loc')  # rename loc to field for clarity
        e.pop('url')  # remove url from error response

    return error(
        description=errors,
        req=req,
        title=title,
    )


def validate_request_body(req: FalconRequest, model: type[BaseModel]):
    """."""
    if model is not None:
        try:
            if isinstance(req.media, list):
                req.context.body = parse_obj_as(list[model], req.media)
            elif isinstance(req.media, dict):
                req.context.body = model(**req.media)

            logger.debug('event=validate-request-body, results=succeeded')
        except falcon.MediaMalformedError as ex:
            err = error(
                description='Error while processing body, malformed JSON provided.',
                exception=traceback.format_exc().replace('\n', ' | '),
                req=req,
                title='Bad Request',
            )
            raise falcon.HTTPBadRequest(**err) from ex
        except ValidationError as ex:
            _process_validation_request_errors(ex, req)
        except Exception as ex:
            err = error(
                description='Error while processing body.',
                exception=traceback.format_exc().replace('\n', ' | '),
                req=req,
                title='Bad Request',
            )
            raise falcon.HTTPBadRequest(**err) from ex


def validate_request_form_data(req: FalconRequest, model: type[BaseModel]):
    """."""
    if model is not None:
        # build model schema data for future lookups
        # "properties": {
        #     "file": {
        #          "title": "File",
        #          "description": "Multi-part file data.",
        #          "allOf": [
        #            {
        #              "$ref": "#/definitions/MultipartFormDataModel"
        #            }
        #          ]
        #     },
        binary_fields = []
        for field, data in model.model_json_schema()['properties'].items():
            for ref in data.get('allOf', []):
                if ref.get('$ref') == '#/$defs/MultipartFormDataModel':
                    binary_fields.append(field)

        try:
            _form_data = {}
            for part in req.media:
                logger.debug(
                    'event=validate-request-form-data, '
                    f'part-name={part.name}, binary-fields={binary_fields}'
                )

                # https://falcon.readthedocs.io/en/stable/api/multipart.html#body-part-type
                # if part.name in binary_fields and part.content_type == 'application/octet-stream':
                if part.name in binary_fields:
                    _form_data[part.name] = {
                        'content': part.stream.read(),
                        'content_type': part.content_type,
                        'filename': part.filename,
                        'name': part.name,
                    }
                else:
                    _form_data[part.name] = part.text

            req.context.form_data = model(**_form_data)
            logger.debug('event=validate-request-form-data, results=succeeded')
        except ValidationError as ex:
            _process_validation_request_errors(ex, req)


def validate_request_headers(req: FalconRequest, model: type[BaseModel]):
    """."""
    if model is not None:
        try:
            req.context.headers = model(**req.headers)
            logger.debug('event=validate-request-headers, results=succeeded')
        except ValidationError as ex:
            _process_validation_request_errors(ex, req)


def validate_request_query_params(req: FalconRequest, model: type[BaseModel]):
    """."""
    if model is not None:
        try:
            # logger.debug(f'event=validate-request-query-params, params={req.params}')
            req.context.params = model(**req.params)
            logger.debug('event=validate-request-query-params, results=succeeded')
        except ValidationError as ex:
            _process_validation_request_errors(ex, req)


def validate_response_body(req: FalconRequest, resp: FalconResponse, model: type[BaseModel]):
    """."""
    if model is not None:
        try:
            if isinstance(resp.media, list):
                resp.media = [model(**m).dict(by_alias=True) for m in resp.media]
            elif isinstance(resp.media, dict):
                resp.media = model(**resp.media).dict(by_alias=True)
            logger.debug('event=validate-response-body, results=succeeded')
        except ValidationError as ex:
            _process_validation_response_errors(ex, req)


def validate_response_headers(req: FalconRequest, resp: FalconResponse, model: type[BaseModel]):
    """."""
    if model is not None:
        try:
            model(**resp.headers)
            logger.debug('event=validate-response-headers, results=succeeded')
        except ValidationError as ex:
            _process_validation_response_errors(ex, req)
