"""Onboarding gate API endpoint."""

from pydantic import ValidationError

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.endpoint.tcvf.settings_resource import build_candidate
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.model.onboarding_model import RECORD_ID, OnboardingModel


class OnboardingResource(EndpointBase):
    """GET/POST/DELETE /api/onboarding"""

    def on_get(self, _req: FalconRequest, resp: FalconResponse):
        """Report whether onboarding has been completed.

        The UI hard-gates on this, so it is answered from the record's existence alone.
        """
        record = self._record()
        resp.media = {
            'completed': record is not None,
            'completed_at': record.completed_at if record else None,
        }

    def on_post(self, req: FalconRequest, resp: FalconResponse):
        """Save the stepper's settings, then record onboarding as complete.

        Settings go through `build_candidate` — the same path
        `PUT /api/settings` uses — so the stepper cannot drift from the Settings page.
        The completion record is written only after the settings actually applied.
        """
        try:
            record = build_candidate(self.settings.app_settings, req.media or {})
        except ValidationError as ex:
            resp.status = '400 Bad Request'
            resp.media = {'completed': False, 'errors': ex.errors()}
            return

        self.settings.app_settings = record
        self.db.save(record)

        completion = OnboardingModel()
        self.db.save(completion)
        self.log.info(f'action=onboarding, status=completed, at={completion.completed_at}')
        resp.media = {
            'completed': True,
            'completed_at': completion.completed_at,
            'settings': record.dict(),
        }

    def on_delete(self, _req: FalconRequest, resp: FalconResponse):
        """Remove the completion record so the stepper re-arms.

        Idempotent by design. This is the only escape hatch out of a hard gate, so it
        never 404s, never depends on the stepper's own state, and treats an already-absent
        record as success.
        """
        record = self._record()
        if record is not None:
            try:
                self.db.delete(record)
            except FileNotFoundError:
                record = None
        self.log.info(f'action=onboarding-reset, status=complete, deleted={record is not None}')
        resp.media = {'completed': False, 'deleted': record is not None}

    def _record(self) -> OnboardingModel | None:
        """Return the completion record, or None when onboarding has not been done."""
        try:
            return self.db.load(OnboardingModel, RECORD_ID)
        except FileNotFoundError:
            return None
