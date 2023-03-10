"""Request and Response validation middleware."""
# standard library
from typing import TYPE_CHECKING

# third-party
from more.validation import (
    response_media,
    validate_request_body,
    validate_request_form_data,
    validate_request_headers,
    validate_request_query_params,
    validate_response_body,
    validate_response_headers,
)

if TYPE_CHECKING:
    # third-party
    import falcon


# pylint: disable=unused-argument
class ValidationMiddleware:
    """Request and Response validation middleware."""

    def process_resource(
        self, req: 'falcon.Request', _resp: 'falcon.Response', resource: object, _param: dict
    ):
        """Process resource method."""
        # inject response_media method in resource
        resource.response_media = response_media

        # validate request using defined models
        if hasattr(resource, 'validation_models') and isinstance(resource.validation_models, dict):
            # get the request validation
            models = resource.validation_models.get(req.method, {}).get('request', {})

            validate_request_body(req, models.get('body'))
            validate_request_headers(req, models.get('headers'))
            validate_request_query_params(req, models.get('query_params'))

            if req.content_type and 'multipart/form-data' in req.content_type:
                validate_request_form_data(req, models.get('form_data'))

    def process_response(
        self, req: 'falcon.Request', resp: 'falcon.Response', resource: object, _req_succeeded: bool
    ):
        """Process response method."""

        # validate request using defined models
        if (
            hasattr(resource, 'validation_models')
            and isinstance(resource.validation_models, dict)
            and _req_succeeded is True
        ):
            # get the request validation
            models = resource.validation_models.get(req.method, {}).get('response', {})

            validate_response_body(req, resp, models.get('body'))
            validate_response_headers(req, resp, models.get('headers'))
