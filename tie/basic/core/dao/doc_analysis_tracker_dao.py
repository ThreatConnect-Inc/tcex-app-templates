"""DAO for ReportPdfTrackerModel."""

from core.json_db import JsonDB, SortBy, SortOrder
from core.json_db.dao import JsonDBDAO
from core.model.tie import DocAnalysisTrackerModel


class DocAnalysisTrackerDAO(JsonDBDAO[DocAnalysisTrackerModel]):
    """Data Access Object for ReportPdfTrackerModel"""

    def __init__(self, db: JsonDB) -> None:
        """Initialize class properties."""
        super().__init__(db, DocAnalysisTrackerModel)

    def find_next_for_group(self, group_id: int) -> DocAnalysisTrackerModel | None:
        """Find next tracker for group."""
        for m in self.db.load_all(self.model, sort_by=SortBy.INDEX, sort_order=SortOrder.DESC):
            if int(m.group_id) == group_id:
                return m
        return None

    def find_groups(self, group_ids: list[int] | None) -> list[DocAnalysisTrackerModel]:
        """Find trackers for groups."""
        models = []
        for m in self.db.load_all(self.model, sort_by=SortBy.INDEX, sort_order=SortOrder.DESC):
            if group_ids is None or int(m.group_id) in group_ids:
                models.append(m)
        return models
