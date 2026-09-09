"""Settings Module"""

# REVIEW (template cleanup, 2026-08-25): retained pending a decision -- confirm with the
# team whether this is a supported extension point for app authors or leftover.
# It was proposed for deletion, then kept because "no importers" does not prove much
# in a template: files here exist to be used by apps built FROM it.
# Evidence at the time:
#   Its sibling core/model/tcvf/settings_model_base.py IS used (2 apps), but nothing imports
#   this one. Note the settings rework moved admin-editable values onto AppSettings
#   (core/model/settings_model_base.py), which may have superseded it.

from pydantic import BaseModel


class AdvancedSettingsModelBase(BaseModel):
    """Advanced Settings model for the App."""

    backfill: int = 48  # How far back to backfill in hours
    backfill_frequency: int = 8  # How often a new backfill job is created in hours
    frequency: int = 1  # How often a new scheduled job is created in hours
