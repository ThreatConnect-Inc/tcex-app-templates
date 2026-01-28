"""Supervisor configuration model."""

# standard library
from datetime import datetime

# third-party
from pydantic import BaseModel, Field, root_validator


class SupervisorConfigModel(BaseModel):
    """Pydantic model for Supervisor configuration - persisted via JsonDB."""

    # Note: Using Field directly instead of Index because Index has a bug where it
    # passes both default and default_factory to Field, which pydantic doesn't allow.
    id: str = Field(default='supervisor_config')

    # Backoff config (used by compute_backoff for per-job retry scheduling)
    backoff_base_seconds: float = Field(
        default=300.0,
        gt=0,
        description='Base backoff duration in seconds (default 5 minutes)',
    )
    backoff_max_seconds: float = Field(
        default=10800.0,
        gt=0,
        description='Maximum backoff duration in seconds (default 3 hours)',
    )
    backoff_jitter: float = Field(
        default=0.1,
        ge=0,
        le=1,
        description='Jitter percentage for backoff randomization (default +/-10%)',
    )

    # Per-pipeline manual override (pipeline_name -> reset timestamp)
    # Only set via API POST - allows manual recovery from stale state
    # Used as alternative to job history for staleness detection
    pipeline_baseline: dict[str, datetime] = Field(
        default_factory=dict,
        description='Manual override timestamps set via API POST. Not set on startup.',
    )

    # Per-pipeline probation tracking (pipeline_name -> probation job request_id or None)
    # None means pipeline is on probation but awaiting first job assignment
    # A request_id means that specific job must complete the full pipeline or app shuts down
    pipelines_on_probation: dict[str, str | None] = Field(
        default_factory=dict,
        description='Pipelines on probation after stale restart. Maps to probation job ID or None.',
    )

    @root_validator
    def _validate_max_greater_than_base(cls, values):  # noqa: N805
        """Ensure backoff_max_seconds >= backoff_base_seconds."""
        base = values.get('backoff_base_seconds')
        max_val = values.get('backoff_max_seconds')
        if base is not None and max_val is not None and max_val < base:
            raise ValueError(
                f'backoff_max_seconds ({max_val}) must be >= backoff_base_seconds ({base})'
            )
        return values
