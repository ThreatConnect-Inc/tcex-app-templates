"""App Inputs"""

from datetime import timedelta

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator
from tcex.input.model.app_feed_api_service_model import AppFeedApiServiceModel

from core.model.settings_model_base import DEFAULT_FAILURE_THRESHOLD
from core.service.notification_service import DIGEST_INTERVAL_MAP, NOTIFICATION_TYPES


class AdvancedSettingsModel(BaseModel):
    """Advanced Settings model for the App."""

    model_config = ConfigDict(extra='forbid')

    backfill: int = 8  # How far back to backfill in hours
    backfill_frequency: int = 8  # How often a new backfill job is created in hours
    frequency: int = 1  # How often a new scheduled job is created in hours
    failure_threshold: timedelta = DEFAULT_FAILURE_THRESHOLD  # Pipeline staleness for app shutdown
    max_retries: int = 10  # Max retries for individual jobs before permanent failure

    @field_serializer('failure_threshold')
    @classmethod
    def serialize_failure_threshold(cls, v: timedelta) -> float:
        """Serialize timedelta to total seconds."""
        return v.total_seconds()

    @field_validator('failure_threshold', mode='before')
    @classmethod
    def parse_failure_threshold(cls, value: str | float | timedelta) -> timedelta:
        """Convert hours (int/string) or seconds (float from JSON) to timedelta."""
        if isinstance(value, timedelta):
            return value
        if isinstance(value, float):
            # From JSON deserialization (stored as total_seconds)
            return timedelta(seconds=value)
        # From user input (hours as int or string)
        return timedelta(hours=int(value))


class AppBaseModel(AppFeedApiServiceModel):
    """Base model for the App containing any common inputs."""

    # vv: ${OWNERS}
    # tc_owner: str
    sample_types: set[str] | None = Field(default_factory=set)
    notification_digest_interval: timedelta = Field(default=timedelta(hours=2))
    notification_types: list[str] = Field(
        default=['app_startup', 'job_retrying', 'job_failed', 'job_recovered']
    )
    # ${ORGANIZATION:TEXT:Advanced Settings}
    advanced_settings: AdvancedSettingsModel = AdvancedSettingsModel()

    @field_validator('notification_digest_interval', mode='before')
    @classmethod
    def parse_digest_interval(cls, value: str | timedelta) -> timedelta:
        """Convert Choice value to timedelta."""
        if isinstance(value, timedelta):
            return value
        return DIGEST_INTERVAL_MAP.get(str(value), timedelta(hours=2))

    @field_validator('notification_types', mode='before')
    @classmethod
    def parse_notification_types(cls, value: list) -> list[str]:
        """Map display labels to internal values."""
        return [NOTIFICATION_TYPES[v].category if v in NOTIFICATION_TYPES else v for v in value]

    @field_validator('sample_types', mode='before')
    @classmethod
    def validate_sample_types(cls, entries: str | None) -> set[str]:
        """Validate and parse the supported types."""
        if not entries:
            return set()

        return {entry.strip().lower() for entry in entries}

    @field_validator('advanced_settings', mode='before')
    @classmethod
    def validate_advanced_settings(cls, entries: str | None) -> dict:
        """Validate and parse the advanced settings."""
        if not entries:
            return {}

        advanced_settings = {}
        ignored_keys = {
            'backfill',
            'backfill_frequency',
            'frequency',
            'backfill_frequency_large',
        }

        for entry in entries.split(','):
            key_value = entry.split('=', maxsplit=1)
            if len(key_value) == 1:
                continue  # Skip if there's no value

            key, value = key_value
            key = key.strip().lower()

            if key in ignored_keys or not key:
                continue  # Skip ignored or empty keys

            if key in advanced_settings:
                msg = f'Duplicate key "{key}" defined in Advanced Settings input.'
                raise ValueError(msg)

            advanced_settings[key] = value

        return advanced_settings


class AppInputs:
    """App Inputs"""

    def __init__(self, inputs: BaseModel):
        """Initialize class properties."""
        self.inputs = inputs

    def update_inputs(self):
        """Add custom App models to inputs.

        Input will be validate when the model is added an any exceptions will
        cause the App to exit with a status code of 1.
        """
        self.inputs.add_model(AppBaseModel)
