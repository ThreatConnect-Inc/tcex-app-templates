"""Settings API endpoints.

Generic. The app declares which settings exist, twice and only twice: on the form
(`UIConfigBuilder.settings_form`) and on the record (`AppSettings`), under matching names.
Nothing here knows the field list.
"""

from pydantic import ValidationError

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.json_db import SortBy, SortOrder
from core.model.onboarding_model import OnboardingModel, is_onboarding_complete
from core.model.settings_revision_model import (
    MAX_REVISIONS,
    SettingsRevisionModel,
    append_revision,
)


def build_candidate(record, payload: dict):
    """Return a validated copy of `record` with `payload` merged over it.

    The whole update path. The record is flat and named exactly as the form posts, so
    pydantic does the work — it validates types, runs the field converters (whole hours
    back into `failure_threshold`'s timedelta), and drops keys the model does not declare.
    A partial payload is fine: unlisted fields keep their current value.

    `id` is stripped so a payload cannot repoint the singleton at another record.
    """
    payload = {key: value for key, value in payload.items() if key != 'id'}
    return type(record)(**{**record.dict(), **payload})


class SettingsResource(EndpointBase):
    """GET/PUT /api/settings"""

    def on_get(self, _req: FalconRequest, resp: FalconResponse):
        """Return the stored settings.

        Only the record is served. Credentials are not on it, so there is nothing here
        that has to remember to exclude them.
        """
        resp.media = self.settings.app_settings.dict()

    def on_put(self, req: FalconRequest, resp: FalconResponse):
        """Apply a settings change and persist it."""
        record = self.settings.app_settings
        try:
            candidate = build_candidate(record, req.media or {})
        except ValidationError as ex:
            resp.status = '400 Bad Request'
            resp.media = {'applied': False, 'errors': ex.errors()}
            return

        before = record.dict()
        after = candidate.dict()
        changed = {
            name: {'from': before[name], 'to': after[name]}
            for name in before
            if before[name] != after[name]
        }

        # Rebind rather than mutate: every reader goes through `settings.app_settings` at
        # use time, so they all pick this up on the next cycle without a restart. Anything
        # that caches a VALUE off the record in __init__ will not — see `Scheduler`.
        self.settings.app_settings = candidate
        self.db.save(candidate)
        append_revision(self.db, SettingsRevisionModel(changed_fields=changed, values=after))

        # A deliberate save IS onboarding. `append_revision` above is reached from nowhere
        # else — not from `AppSettings.load`'s first-boot seed, not from
        # `POST /api/onboarding` — so getting here means a human chose these values. Writing
        # the completion record makes "onboarding complete" mean the same thing by either
        # route, and closes the configured-but-permanently-gated trap for installs
        # configured over the API. (The UI hides Save while gated, so this is not a
        # browser-side escape hatch — see the Settings page.) Idempotent: the record is a
        # singleton keyed on RECORD_ID and carries no state worth overwriting.
        #
        # Placement is load-bearing: after the save and after `append_revision`, so a
        # payload that fails `build_candidate` never marks onboarding complete.
        if not is_onboarding_complete(self.db):
            completion = OnboardingModel()
            self.db.save(completion)
            self.log.info(
                f'action=onboarding-auto-complete, status=completed, reason=settings-saved, '
                f'completed-at={completion.completed_at}'
            )

        self.log.info(f'action=settings-apply, status=applied, changed={sorted(changed)}')
        resp.media = {'applied': True, 'changed_fields': changed, 'settings': after}


class SettingsRevisionsResource(EndpointBase):
    """GET /api/settings/revisions"""

    def on_get(self, _req: FalconRequest, resp: FalconResponse):
        """Return the settings revision history, newest first."""
        revisions = self.db.load_all(
            SettingsRevisionModel,
            sort_by=SortBy.INDEX,
            sort_order=SortOrder.DESC,
            limit=MAX_REVISIONS,
        )
        resp.media = [revision.dict() for revision in revisions]
