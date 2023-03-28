"""Falcon Validation hook module."""
# standard library
import json
import logging
import traceback
from typing import TYPE_CHECKING, Optional, Union

# third-party
import falcon
from model import PaginatorResponseModel
from more import error
from pydantic import ValidationError, parse_obj_as

if TYPE_CHECKING:
    # third-party
    from more import Base, Paginator
    from pydantic import BaseModel

# get primary API logger
logger = logging.getLogger('tcex')


def _process_validation_request_errors(ex: 'ValidationError', req: 'falcon.Request'):
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


def _process_validation_response_errors(ex: 'ValidationError', req: 'falcon.Request'):
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
    ex: 'ValidationError', title: str, req: Optional['falcon.Request'] = None
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


def response_media(
    req: 'falcon.Request',
    db_data: Union['Base', list['Base']],
    model: 'BaseModel',
    params: 'BaseModel',
    paginator: Optional['Paginator'] = None,
    from_orm: bool = True,
) -> dict:
    """Apply field filters and return response text."""
    json_param = {
        'exclude': params.exclude_filter,
        'exclude_defaults': params.exclude_defaults,
        'exclude_none': params.exclude_none,
        'exclude_unset': params.exclude_unset,
        'include': params.include_filter,
        'sort_keys': True,
    }
    try:
        if isinstance(db_data, list):
            # handle collection response
            if from_orm is True:
                media = [json.loads(model.from_orm(a).json(**json_param)) for a in db_data]
            else:
                media = [json.loads(model(**a).json(**json_param)) for a in db_data]
        else:
            # handle item response
            if from_orm is True:
                media = json.loads(model.from_orm(db_data).json(**json_param))
            else:
                media = json.loads(model(**db_data).json(**json_param))

        if paginator is not None:
            paginated_data = {
                'count': len(media),
                'data': media,
                'next': paginator.next_url,
                'previous': paginator.previous_url,
                'total_count': paginator.total_count,
            }
            media = PaginatorResponseModel(**paginated_data).dict(exclude_none=True)

        return media
    except ValidationError as ex:
        err = format_validation_errors(ex, 'Internal Server Error', req)
        raise falcon.HTTPInternalServerError(**err) from ex
    except Exception as ex:
        err = error(
            description='Error while creating response.',
            exception=traceback.format_exc().split('\n'),
            req=req,
            title='Internal Server Error',
        )
        raise falcon.HTTPInternalServerError(**err) from ex


def validate_request_body(req: 'falcon.Request', model: 'BaseModel'):
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


def validate_request_form_data(req: 'falcon.Request', model: 'BaseModel'):
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


def validate_request_headers(req: 'falcon.Request', model: 'BaseModel'):
    """Validate request headers."""
    if model is not None:
        try:
            req.context.headers = model(**req.headers)

            logger.debug('event=validate-request-headers, results=succeeded')
        except ValidationError as ex:
            _process_validation_request_errors(ex, req)


def validate_request_query_params(req: 'falcon.Request', model: 'BaseModel'):
    """Validate request query parameters."""
    if model is not None:
        try:
            req.context.params = model(**req.params)

            logger.debug('event=validate-request-query-params, results=succeeded')
        except ValidationError as ex:
            _process_validation_request_errors(ex, req)


def validate_response_body(req: 'falcon.Request', resp: 'falcon.Response', model: 'BaseModel'):
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


def validate_response_headers(req: 'falcon.Request', resp: 'falcon.Response', model: 'BaseModel'):
    """Validate request headers."""
    if model is not None:
        try:
            model(**resp.headers)

            logger.debug('event=validate-response-headers, results=succeeded')
        except ValidationError as ex:
            _process_validation_response_errors(ex, req)
