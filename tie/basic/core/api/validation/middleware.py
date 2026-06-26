"""Request and Response validation middleware."""

from __future__ import annotations

import traceback
from typing import Any, get_type_hints

import falcon

from core.api.error.util import error
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.middleware_abc import MiddlewareABC
from core.api.validation.util import (
    validate_request_body,
    validate_request_form_data,
    validate_request_headers,
    validate_request_query_params,
)


class ValidationMiddleware(MiddlewareABC):
    """Request and Response validation middleware."""

    def process_resource(
        self, req: FalconRequest, _resp: FalconResponse, resource: Any, params: dict
    ):
        """Process resource method."""
        try:
            annotations = get_type_hints(getattr(resource, f'on_{req.method.lower()}'))
        except AttributeError as ex:
            err = error(
                description=(f'{req.method} is not Allowed.'),
                exception=traceback.format_exc().replace('\n', ' | '),
                title='Method is not Allowed',
            )
            raise falcon.HTTPMethodNotAllowed([], **err) from ex

        # dynamically set params based on method annotations
        for name, annotation in annotations.items():
            match name:
                case 'body':
                    validate_request_body(req, annotation)
                    params['body'] = req.context.body

                case 'headers':
                    validate_request_headers(req, annotation)
                    params['headers'] = req.context.headers

                case 'form_data':
                    if req.content_type and 'multipart/form-data' in req.content_type:
                        validate_request_form_data(req, annotation)
                        params['form_data'] = req.context.form_data
                    else:
                        err = error(
                            description='Missing Content-Type: multipart/form-data header.',
                            req=req,
                            title='Bad Request',
                        )
                        raise falcon.HTTPBadRequest(**err)

                case 'query_params':
                    validate_request_query_params(req, annotation)
                    params['query_params'] = req.context.params
