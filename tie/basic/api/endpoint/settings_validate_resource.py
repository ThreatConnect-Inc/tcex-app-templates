"""Settings validation for this App.

The EXAMPLE app-side half of `POST /api/settings/validate`. Subclass
`SettingsValidateResourceBase`, implement `validations()`, and the route in
`core/app/enums.py` picks this class up by optional import — there is nothing to register.

Replace the checks below with the ones worth running for this App. Each is one
`self.check(...)` call; see `SettingsValidateResourceBase.check` for what a check may
return and when it blocks a save.
"""

from datetime import timedelta

from core.api.endpoint.tcvf.settings_validate_resource import SettingsValidateResourceBase

# A failure threshold shorter than a couple of poll intervals marks healthy jobs as stale
# before they have had a chance to finish a single cycle.
MIN_THRESHOLD_MULTIPLE = 2


class SettingsValidateResource(SettingsValidateResourceBase):
    """POST /api/settings/validate"""

    def _sample_types_exist(self, configured) -> bool:
        """True when every configured sample type is in the catalogue.

        An empty catalogue means the lookup failed, not that nothing exists — reporting
        "not found" then would be a lie, so it passes and lets the connection check own
        that failure.
        """
        catalogue = self.settings.all_sample_types
        if not configured or not catalogue:
            return True

        known = {str(entry).strip().lower() for entry in catalogue}
        return all(str(entry).strip().lower() in known for entry in configured)

    def validations(self, candidate) -> list[dict]:
        """Checks run against a candidate settings payload.

        Order is the contract: connectivity first, so an unreachable service reports as a
        connection failure rather than as a confusing downstream error.
        """
        threshold = candidate.failure_threshold
        minimum = timedelta(hours=candidate.frequency) * MIN_THRESHOLD_MULTIPLE

        return [
            self.check(
                # A CALLABLE, not a call — see `SettingsValidateResourceBase.check`.
                fn=lambda: self.sdk.test_connection(self.settings),
                success='API connection: the vendor API is reachable.',
                error=(
                    'API connection: could not reach the vendor API. Confirm the service '
                    'URL and API key are correct, that the key has not been revoked, and '
                    'that the ThreatConnect server can reach the service'
                ),
            ),
            self.check(
                fn=lambda: self._sample_types_exist(candidate.sample_types),
                success=(
                    f'Sample types: all {len(candidate.sample_types)} resolved — only '
                    'matching objects will be ingested.'
                    if candidate.sample_types
                    else 'Sample types: none configured — everything will be ingested.'
                ),
                error=(
                    'Sample types: could not resolve every entry. Check each one against '
                    'the types this deployment supports — matching is case-insensitive'
                ),
            ),
            self.check(
                fn=lambda: threshold >= minimum,
                success=(
                    f'Poll frequency: polling every {_hours(timedelta(hours=candidate.frequency))} '
                    f'leaves plenty of room under a failure threshold of {_hours(threshold)}.'
                ),
                error='',
                # Unwise, not broken — cross-field semantics the form cannot express.
                # Getting it wrong silently marks healthy jobs stale, but it is a bad
                # configuration rather than an unusable one, so it must not block a save.
                warning=(
                    f'Poll frequency: a failure threshold of {_hours(threshold)} is shorter '
                    f'than {MIN_THRESHOLD_MULTIPLE} poll intervals of '
                    f'{_hours(timedelta(hours=candidate.frequency))}, so healthy jobs may be '
                    f'marked stale before they finish a cycle. Raise the threshold to at '
                    f'least {_hours(minimum)}, or lower the poll frequency.'
                ),
            ),
        ]


def _hours(value: timedelta) -> str:
    """Render a duration as whole hours, pluralised. These strings are read by operators."""
    hours = value.total_seconds() / 3600
    return f'{hours:g} hour' if hours == 1 else f'{hours:g} hours'
