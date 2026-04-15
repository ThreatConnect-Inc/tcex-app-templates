"""Define custom settings for app.

The parent SettingsModel class should never be edited.
"""

from datetime import timedelta

from pydantic import Field

from app_inputs import AdvancedSettingsModel
from core.json_db import Embedded
from core.model.settings_model_base import SettingModelBase


class SettingModel(SettingModelBase):
    """Custom Setting Model"""

    advanced_settings: AdvancedSettingsModel = Embedded()

    # Define custom settings for the App
    sample_types: set[str]
    notification_digest_interval: timedelta | None = Field(default=None)
    notification_types: list[str] | None = Field(default=None)
