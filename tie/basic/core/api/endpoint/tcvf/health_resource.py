"""Class for /api/health endpoint - always succeeds if app is up."""

# standard library
import os
from datetime import UTC, datetime

# third-party
import falcon

# first-party
from core.api.endpoint.tcvf.endpoint_base import EndpointBase

# Capture start time at module load for uptime calculation
_START_TIME = datetime.now(UTC)


class HealthResource(EndpointBase):
    """Health check endpoint.

    This endpoint ALWAYS returns HTTP 200 if the application is running.
    Used by external systems (load balancers, orchestrators) to determine
    if the application is up and responsive.
    """

    def on_get(self, req: falcon.Request, resp: falcon.Response):  # noqa: ARG002
        """Handle GET requests - return health status."""
        now = datetime.now(UTC)
        uptime_seconds = (now - _START_TIME).total_seconds()

        resp.media = {
            'status': 'ok',
            'timestamp': now.isoformat(),
            'uptime_seconds': uptime_seconds,
            'pid': os.getpid(),
        }
        resp.status = falcon.HTTP_200
