"""Settings validation endpoint.

An app declares its checks by subclassing `SettingsValidateResourceBase` and implementing
`validations()` — one `self.check(...)` call per thing worth verifying. Everything else
(building the candidate, running the checks, the response shape) lives here.
"""

from collections.abc import Callable

from pydantic import ValidationError

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.endpoint.tcvf.settings_resource import build_candidate
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse

#: A genuinely broken thing — the app cannot do its job with this configuration.
SEVERITY_ERROR = 'error'
#: A merely unwise thing. Reported clearly, never blocks a save.
SEVERITY_WARNING = 'warning'


class SettingsValidateResourceBase(EndpointBase):
    """POST /api/settings/validate"""

    def validations(self, _candidate) -> list[dict]:
        """Return the checks to run against the candidate. Apps override this.

        Underscored here because the base has no checks of its own to run against it —
        an app that overrides this names the argument and uses it.

        `candidate` is a throwaway copy of the settings record with the posted payload
        applied, so a check sees exactly what a save would produce without anything
        having been saved.
        """
        return []

    def check(
        self,
        fn: Callable,
        success: str,
        error: str,
        warning: str | None = None,
    ) -> dict:
        """Run one check and return its result.

        `fn` is a CALLABLE, not a call — `fn=self.sdk.test_connection`, not
        `fn=self.sdk.test_connection()`. Passing the result would run the check while the
        list is being built, so a raise would escape before anything could report it.

        Outcomes:
        * raises              -> failure. The exception is appended to `error`.
        * returns `None`      -> pass. A check that signals only by raising says nothing
                                 on success, and should not have to `return True` to be
                                 believed.
        * returns other falsy -> failure, as `warning` if one was given, else `error`.
                                 This is what lets a check be a plain comparison.
        * returns truthy      -> pass, reported as `success`.

        Supplying `warning` is how a check says "unwise, not broken": it is surfaced but
        does not stand between the operator and Save.
        """
        try:
            passed = fn()
        except Exception as ex:
            self.log.exception(f'action=settings-validate, status=raised, message={error}')
            return {
                'passed': False,
                'severity': SEVERITY_ERROR,
                'message': f'{error} — {ex}',
            }

        if passed is None or passed:
            return {'passed': True, 'severity': SEVERITY_ERROR, 'message': success}

        if warning is not None:
            return {'passed': False, 'severity': SEVERITY_WARNING, 'message': warning}
        return {'passed': False, 'severity': SEVERITY_ERROR, 'message': error}

    def on_post(self, req: FalconRequest, resp: FalconResponse):
        """Validate a candidate settings payload.

        Read-only. The candidate is a deep copy and the live settings are never touched —
        applying is the job of `PUT /api/settings`.

        `passed` reflects blocking failures only, so a warning reports without gating.
        """
        try:
            candidate = build_candidate(self.settings.app_settings, req.media or {})
        except ValidationError as ex:
            resp.status = '400 Bad Request'
            resp.media = {'passed': False, 'checks': [], 'errors': ex.errors()}
            return

        checks = self.validations(candidate)
        blocking = [c for c in checks if not c['passed'] and c['severity'] == SEVERITY_ERROR]
        resp.media = {'passed': not blocking, 'checks': checks}
