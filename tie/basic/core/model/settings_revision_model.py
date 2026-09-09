"""Audit trail of settings changes.

THE STORAGE PATH IS DERIVED FROM THIS MODULE PATH AND CLASS NAME — see the note at the
top of `model/settings_model.py`. Do not move or rename either.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from core.json_db import Index, JsonDB, SortBy, SortOrder

# Ring buffer depth. Revisions are an operator audit aid, not a data store.
MAX_REVISIONS = 100


class SettingsRevisionModel(BaseModel):
    """One settings change: what changed, when, and the resulting snapshot."""

    # Index() defaults to a uuid7 factory, which is time-ordered — so sorting by INDEX
    # is chronological and the ring-buffer trim is just "drop the oldest".
    id: str = Index()
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    changed_fields: dict[str, dict] = Field(default_factory=dict)
    values: dict = Field(default_factory=dict)


def append_revision(db: JsonDB, revision: SettingsRevisionModel) -> None:
    """Save a revision, then trim the ring buffer down to the newest MAX_REVISIONS."""
    db.save(revision)
    stored = list(
        db.load_all(SettingsRevisionModel, sort_by=SortBy.INDEX, sort_order=SortOrder.ASC)
    )
    for stale in stored[:-MAX_REVISIONS]:
        db.delete(stale)
