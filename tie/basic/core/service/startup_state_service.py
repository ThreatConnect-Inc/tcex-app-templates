"""Startup state reconciliation.

Runs once per boot to bring the JSON DB in line with what this install already is.

An app that has run before must not be pushed back through first-run onboarding. The
onboarding record only ever gets written by an admin clicking through the stepper
(`core/api/endpoint/tcvf/onboarding_resource.py`), so without this an upgrade would leave a
fully-configured, previously-running app with no record — both schedulers would hit their
onboarding gate and ingestion would silently stop.

DELIBERATELY NOT A REGISTERED MIGRATION. `MigrationService.register_migration()` cannot
carry this: `preform_migrations()` returns early on the first boot that has no
`VersionManagerModel`, so an app old enough to lack that tracker would never run the
migration — precisely the app this exists to protect. It also never advances
`migration_tracker.version`, so registered migrations re-run every boot. This is an
explicit, idempotent startup step instead.

CALL ORDER MATTERS — see `core/app/api_service_falcon_abc.py::loop_forever`. This must run
AFTER `preform_migrations()` (which imports old job records out of the legacy sqlite DB;
checking job history first would misread a sqlite-era app as a fresh install), BEFORE
`_remove_pending_jobs()` (which deletes job records, so an app whose only jobs were pending
at shutdown would look fresh), and BEFORE the `schedule.run_pending()` loop, so no
scheduler tick ever observes the ungated state.
"""

import logging
from typing import TYPE_CHECKING, cast

from tcex.logger.trace_logger import TraceLogger

from core.model.onboarding_model import OnboardingModel, is_onboarding_complete

if TYPE_CHECKING:
    from core.dao.job_dao import JobRequestDAO
    from core.json_db import JsonDB

logger: TraceLogger = cast('TraceLogger', logging.getLogger('tcex'))


class StartupStateService:
    """Reconcile persisted app state once per boot."""

    def __init__(
        self,
        db: 'JsonDB',
        job_dao: 'JobRequestDAO',
        log: TraceLogger | None = None,
    ):
        """Initialize class properties."""
        self.db = db
        self.job_dao = job_dao
        self.log = log or logger

    def reconcile(self):
        """Perform every startup reconciliation step."""
        self.auto_complete_onboarding()

    def auto_complete_onboarding(self):
        """Mark onboarding complete when this app has clearly run before.

        Prior job history in the JSON DB is the signal. `tc_out_path/json_db` survives an
        app upgrade on the TC platform, so jobs on disk mean this install was already
        deployed, configured and ingesting before the onboarding gate existed.

        A partially configured app still auto-completes: ingestion is never blocked on
        incomplete config. The admin fixes what is missing on the Settings page.

        Kept separate from `is_onboarding_complete()` on purpose — that stays a
        side-effect-free predicate (see its docstring).
        """
        # Cheap and idempotent: once the record exists there is nothing to decide, so job
        # history is never even read.
        if is_onboarding_complete(self.db):
            self.log.info(
                'action=onboarding-auto-complete, status=skipped, reason=already-onboarded'
            )
            return

        job_ids = self.job_dao.get_all_job_ids()
        if not job_ids:
            self.log.info(
                'action=onboarding-auto-complete, status=skipped, reason=no-job-history, '
                'detail="fresh install, onboarding stepper will be shown"'
            )
            return

        record = OnboardingModel()
        self.db.save(record)
        self.log.info(
            'action=onboarding-auto-complete, status=completed, reason=prior-job-history, '
            f'job-count={len(job_ids)}, completed-at={record.completed_at}, '
            'detail="app ran before this template version, onboarding stepper skipped so '
            'ingestion continues uninterrupted"'
        )
