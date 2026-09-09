"""Onboarding completion record.

THE STORAGE PATH IS DERIVED FROM THIS MODULE PATH AND CLASS NAME.
`core/json_db/json_db.py` builds the storage directory from
``f'{cls.__module__}.{cls.__name__}'``, so moving or renaming this module — or the
``OnboardingModel`` class — orphans the record already written to disk. An orphaned
record here does not merely lose data: absence of the record is what re-arms the
onboarding gate, so a rename would lock every existing install back into the stepper.
Leave both exactly where they are.
"""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from core.json_db import JsonDB

logger = logging.getLogger('tcex')

# Singleton record id. Also satisfies JsonDB.get_index_field(), which needs either an
# Index()-marked field or a field literally named `id`.
RECORD_ID = 'onboarding'


class OnboardingModel(BaseModel):
    """Marks onboarding as done.

    ABSENCE OF THE RECORD IS THE TRIGGER — there is deliberately no `completed` flag to
    drift out of sync with whether the record exists.
    """

    id: str = RECORD_ID
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def is_onboarding_complete(db: 'JsonDB') -> bool:
    """Return True once the onboarding completion record exists.

    Absence of the record — not a boolean flag — is the signal (see OnboardingModel's own
    docstring above). Call this fresh on every check; do not cache the result on a
    long-lived object (e.g. Tasks, a singleton constructed once at boot,
    core/app/api_service_falcon_abc.py:55) or it will never notice onboarding completing
    later.
    """
    try:
        db.load(OnboardingModel, RECORD_ID)
    except FileNotFoundError:
        return False
    except Exception as ex:
        # The record exists but cannot be read (truncated .gz, invalid JSON, schema
        # drift). `JsonDB.load()` raises rather than returning None for these, and this
        # predicate is called from the schedulers and from `settings_resource.on_put`
        # — letting it propagate turned an unreadable byte into a 500 on every settings
        # save and an exception on the ingest path.
        #
        # Caught broadly on purpose. The narrower (OSError, ValueError) missed EOFError,
        # which is exactly what a gzip truncated by a disk-full write or a container killed
        # mid-save raises — so the failure this handler was written for was the one that
        # still escaped it. FileNotFoundError is handled above and never reaches here.
        #
        # Fail OPEN: a record that exists means this install was onboarded at some
        # point, and re-gating a working app would stop ingestion outright. That matches
        # `auto_complete_onboarding`'s rule that ingestion is never blocked on config.
        logger.warning(
            f'event=onboarding-record-unreadable, action=treating-as-complete, '
            f'error={type(ex).__name__}: {ex}'
        )
        return True
    return True
