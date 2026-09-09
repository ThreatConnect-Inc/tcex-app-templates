"""Falcon Validation hook module."""

# REVIEW (template cleanup, 2026-08-25): retained pending a decision -- confirm with the
# team whether this is a supported extension point for app authors or leftover.
# It was proposed for deletion, then kept because "no importers" does not prove much
# in a template: files here exist to be used by apps built FROM it.
# Evidence at the time:
#   9 of its 10 functions are duplicated in core/api/validation/util.py, which is the copy
#   actually wired up (core/api/validation/middleware.py imports from there). This one has no
#   importers in the template or in any app.

import json
import logging
import traceback
from typing import TypeVar

import falcon
from pydantic import BaseModel, ValidationError, parse_obj_as

from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.validation.models.query_param_filter_model import QueryParamFilterModel
from core.api.validation.util import PaginatorResponseModel
from core.more.error import error
from core.more.paginator import Paginator

# get primary API logger
logger = logging.getLogger('tcex')


def _process_validation_request_errors(ex: ValidationError, req: FalconRequest):
    """Process any validation errors."""
    errors = json.loads(ex.json())
    for e in errors:
        e['field'] = e.pop('loc')

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
        e['field'] = e.pop('loc')

    err = error(
        description=errors,
        req=req,
        title='Internal Server Error',
    )
    raise falcon.HTTPInternalServerError(**err) from ex


# TODO: [low] this could be added to resource via middleware so it would not need to be imported
def format_validation_errors(
    ex: ValidationError, title: str, req: FalconRequest | None = None
) -> dict:
    """Process any validation errors."""
    errors = json.loads(ex.json())
    for e in errors:
        e['field'] = e.pop('loc')

    return error(
        description=errors,
        req=req,
        title=title,
    )


T = TypeVar('T', bound=BaseModel)


def response_media(req: FalconRequest, data: T | Paginator[T]):
    """Apply field filters and return response text."""
    params: QueryParamFilterModel = req.context.params  # type: ignore

    json_param = {
        'exclude': params.exclude_filter,
        'exclude_defaults': params.exclude_defaults,
        'exclude_none': params.exclude_none,
        'exclude_unset': params.exclude_unset,
        'include': params.include_filter,
        'sort_keys': True,
    }
    try:
        if isinstance(data, Paginator):
            # handle collection response
            media = [json.loads(t.json(**json_param)) for t in data.page_data]
            paginated_data = {
                'count': len(media),
                'data': media,
                'next': data.next_url,
                'previous': data.previous_url,
                'total_count': data.total_count,
            }
            media = PaginatorResponseModel(**paginated_data).dict(exclude_none=True)
        else:
            # handle item response
            media = json.loads(data.json(**json_param))

        return media
    except ValidationError as ex:
        err = format_validation_errors(ex, 'Internal Server Error', req)
        raise falcon.HTTPInternalServerError(**err) from ex
    except Exception as ex:
        err = error(
            description='Error while creating response.',
            exception=traceback.format_exc(),
            req=req,
            title='Internal Server Error',
        )
        raise falcon.HTTPInternalServerError(**err) from ex


def validate_request_body(req: FalconRequest, model: BaseModel):
    """Validate request query parameters."""
    if model is not None:
        try:
            # TODO: [med] is there a better way to get json body as dict
            media = req.get_media()

            if isinstance(media, list):
                req.context.body = parse_obj_as(list[model], media)
            elif isinstance(media, dict):
                req.context.body = model(**media)

            logger.debug('event=validate-request-body, results=succeeded')
        except falcon.errors.MediaMalformedError as ex:
            err = error(
                description='Error while processing body, malformed JSON provided.',
                exception=traceback.format_exc().split('\n'),
                req=req,
                title='Bad Request',
            )
            raise falcon.HTTPBadRequest(**err) from ex
        except ValidationError as ex:
            _process_validation_request_errors(ex, req)
        except Exception as ex:
            err = error(
                description='Error while processing body.',
                exception=traceback.format_exc().split('\n'),
                req=req,
                title='Bad Request',
            )
            raise falcon.HTTPBadRequest(**err) from ex


def validate_request_form_data(req: FalconRequest, model: BaseModel):
    """Validate request query parameters."""
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
        for field, data in model.schema().get('properties').items():
            for ref in data.get('allOf', []):
                if ref.get('$ref') == '#/definitions/MultipartFormDataModel':
                    binary_fields.append(field)

        try:
            _form_data = {}
            for part in req.media:
                logger.debug(
                    'event=validate-request-form-data, '
                    f'part-name={part.name}, binary-fields={binary_fields}'
                )

                # https://falcon.readthedocs.io/en/stable/api/multipart.html#body-part-type
                if part.name in binary_fields and part.content_type == 'application/octet-stream':
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


def validate_request_headers(req: FalconRequest, model: BaseModel):
    """Validate request headers."""
    if model is not None:
        try:
            req.context.headers = model(**req.headers)

            logger.debug('event=validate-request-headers, results=succeeded')
        except ValidationError as ex:
            _process_validation_request_errors(ex, req)


def validate_request_query_params(req: FalconRequest, model: BaseModel):
    """Validate request query parameters."""
    if model is not None:
        try:
            req.context.params = model(**req.params)

            logger.debug('event=validate-request-query-params, results=succeeded')
        except ValidationError as ex:
            _process_validation_request_errors(ex, req)


def validate_response_body(req: FalconRequest, resp: FalconResponse, model: BaseModel):
    """Validate request query parameters."""
    if model is not None:
        try:
            if isinstance(resp.media, list):
                for item in resp.media:
                    model(**item)
            else:
                model(**resp.media)

            logger.debug('event=validate-response-body, results=succeeded')
        except ValidationError as ex:
            _process_validation_response_errors(ex, req)


def validate_response_headers(req: FalconRequest, resp: FalconResponse, model: BaseModel):
    """Validate request headers."""
    if model is not None:
        try:
            model(**resp.headers)

            logger.debug('event=validate-response-headers, results=succeeded')
        except ValidationError as ex:
            _process_validation_response_errors(ex, req)
