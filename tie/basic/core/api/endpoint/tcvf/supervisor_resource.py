"""Class for /api/support/supervisor endpoint"""

import falcon
from pydantic import Field
from spectree import Response

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.spec import spec, tag_util
from core.api.validation.models.query_param_model import QueryParamModel
from core.model.model_base import ModelBase


class SupervisorConfigUpdateBody(ModelBase):
    """Request body model for updating supervisor config."""

    backoff_base_seconds: float | None = Field(None, ge=1.0, le=86400.0)
    backoff_max_seconds: float | None = Field(None, ge=1.0, le=86400.0)
    backoff_jitter: float | None = Field(None, ge=0.0, le=1.0)


class PipelineBaselineResetBody(ModelBase):
    """Request body model for resetting pipeline health baselines."""

    pipelines: list[str] | None = None


class SupervisorResource(EndpointBase):
    """Class for /api/support/supervisor endpoint

    Provides endpoints to view and manage the Supervisor state:
    - GET: View current status (pipeline health, backoff config)
    - POST: Reset pipeline health baselines (recover from stale state)
    - PUT: Update configuration (backoff settings)
    """

    @spec.validate(
        resp=Response('HTTP_200'),
        skip_validation=True,
        tags=[tag_util],
    )
    def on_get(self, req: falcon.Request, resp: falcon.Response):  # noqa: ARG002
        """Handle GET requests - return current supervisor status.

        Example output::

            {
                'config': {
                    'backoff_base_seconds': 300.0,
                    'backoff_max_seconds': 7200.0,
                    'backoff_jitter': 0.1,
                    'pipeline_baseline': {},
                    'pipelines_on_probation': {
                        'recorded_future_risk_list': 'abc123-request-id'
                    },
                },
                'pipeline_health': {
                    'recorded_future_risk_list': {
                        'last_completed': '2024-01-15T10:30:00+00:00',
                        'is_stale': false,
                        'threshold_hours': 48,
                    }
                },
            }

        Pipeline health:
        - last_completed: When the pipeline last completed successfully (from job history
          or manual API override). Used for staleness detection.
        - is_stale: True if last_completed > threshold_hours ago
        - threshold_hours: Staleness threshold from settings

        Probation status (in config.pipelines_on_probation):
        - Pipelines enter probation when stale on startup (no jobs completed for threshold)
        - Maps pipeline name -> probation job ID (or null if awaiting first job)
        - If probation job fails, app shuts down immediately
        - If probation job completes full pipeline, probation is cleared
        """
        resp.media = self.tasks.supervisor.get_status()
        resp.status = falcon.HTTP_200

    @spec.validate(
        resp=Response('HTTP_200'),
        query=QueryParamModel,
        skip_validation=True,
        tags=[tag_util],
    )
    def on_post(
        self,
        _req: falcon.Request,
        resp: falcon.Response,
        query_params: QueryParamModel,  # noqa: ARG002
        body: PipelineBaselineResetBody,
    ):
        """Handle POST requests - reset pipeline health baselines.

        Use this to recover from a stale state or to manually reset health tracking.
        If pipelines list is empty or not provided, resets all known pipelines.

        Example input (reset specific pipelines)::

            {'pipelines': ['recorded_future_risk_list']}

        Example input (reset all pipelines)::

            {}

        Example output::

            {
                'message': 'Pipeline baselines reset',
                'reset_pipelines': {
                    'recorded_future_risk_list': '2024-01-15T12:00:00+00:00'
                },
            }
        """
        self.log.info(f'action=api-post-supervisor-reset-baseline, body={body}')

        reset_times = self.tasks.supervisor.reset_pipeline_baseline(body.pipelines)

        resp.media = {
            'message': 'Pipeline baselines reset',
            'reset_pipelines': {k: v.isoformat() for k, v in reset_times.items()},
        }
        resp.status = falcon.HTTP_200

    @spec.validate(
        resp=Response('HTTP_200'),
        query=QueryParamModel,
        skip_validation=True,
        tags=[tag_util],
    )
    def on_put(
        self,
        _req: falcon.Request,
        resp: falcon.Response,
        query_params: QueryParamModel,  # noqa: ARG002
        body: SupervisorConfigUpdateBody,
    ):
        """Handle PUT requests - update supervisor configuration.

        Example input::

            {
                'backoff_base_seconds': 120.0,
                'backoff_max_seconds': 3600.0,
                'backoff_jitter': 0.15,
            }

        Example output::

            {
                'message': 'Configuration updated',
                'config': {
                    'backoff_base_seconds': 120.0,
                    'backoff_max_seconds': 3600.0,
                    'backoff_jitter': 0.15,
                },
            }
        """
        self.log.info(f'action=api-put-supervisor-config, body={body}')

        # Get current config and update only provided fields
        current_config = self.tasks.supervisor.config

        if body.backoff_base_seconds is not None:
            current_config.backoff_base_seconds = body.backoff_base_seconds
        if body.backoff_max_seconds is not None:
            current_config.backoff_max_seconds = body.backoff_max_seconds
        if body.backoff_jitter is not None:
            current_config.backoff_jitter = body.backoff_jitter

        # Persist updated config
        self.db.save(current_config)

        # Reload config in supervisor
        self.tasks.supervisor.reload_config()

        resp.media = {
            'message': 'Configuration updated',
            'config': self.tasks.supervisor.config.model_dump(),
        }
        resp.status = falcon.HTTP_200
