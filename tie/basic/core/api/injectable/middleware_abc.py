"""Declares an abstract base class for Middleware."""

# REVIEW (template cleanup, 2026-08-25): retained pending a decision -- confirm with the
# team whether this is a supported extension point for app authors or leftover.
# It was proposed for deletion, then kept because "no importers" does not prove much
# in a template: files here exist to be used by apps built FROM it.
# Evidence at the time:
#   Duplicates core/api/middleware_abc.py, which is the one everything imports. This version
#   additionally declares process_request/process_resource/process_response as @abstractmethod
#   -- but no middleware in the template implements process_request or process_response, so
#   subclassing this would fail to instantiate.

from abc import ABC, abstractmethod

from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse


class MiddlewareABC(ABC):
    """Abstract base class for all middleware implementations."""

    @abstractmethod
    def process_request(self, req: FalconRequest, resp: FalconResponse):
        """Process the request before routing it."""

    @abstractmethod
    def process_resource(
        self, req: FalconRequest, resp: FalconResponse, resource: object, params: dict
    ):
        """Process the request after routing."""

    @abstractmethod
    def process_response(
        self,
        req: FalconRequest,
        resp: FalconResponse,
        resource: object,
        req_succeeded: bool,
    ):
        """Post-processing of the response (after routing)."""
