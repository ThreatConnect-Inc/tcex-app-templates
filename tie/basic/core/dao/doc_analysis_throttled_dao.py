"""DAO for ReportPdfTrackerModel."""

import arrow

from core.json_db import JsonDB, SortBy, SortOrder
from core.json_db.dao import JsonDBDAO
from core.model.tie import DocAnalysisThrottleModel


class DocAnalysisThrottledDAO(JsonDBDAO[DocAnalysisThrottleModel]):
    """Data Access Object for ReportPdfTrackerModel"""

    def __init__(self, db: JsonDB) -> None:
        """Initialize class properties."""
        super().__init__(db, DocAnalysisThrottleModel)

    def throttled_time_remaining(self) -> int:
        """Check if the task is throttled."""
        instance = self.instance
        if instance.timestamp is None:
            return 0
        tomorrow = int(arrow.utcnow().shift(days=1).floor('day').timestamp())
        return tomorrow - instance.timestamp

    def reset_throttle(self) -> None:
        """Reset the throttle."""
        item = self.instance
        item.timestamp = None
        self.db.save(item)

    @property
    def instance(self) -> DocAnalysisThrottleModel:
        """Return the instance of the throttled item."""
        models = []
        for m in self.db.load_all(self.model, sort_by=SortBy.INDEX, sort_order=SortOrder.DESC):
            models.append(m)
        if len(models) > 1:
            ex_msg = 'Multiple throttled items found, expected only one.'
            raise ValueError(ex_msg)
        if not models:
            model = DocAnalysisThrottleModel()
            self.db.save(model)
        else:
            model = models[0]
        return model

    def throttle(self) -> None:
        """Throttle the group."""
        item = self.instance
        item.timestamp = int(arrow.utcnow().timestamp())
        self.db.save(item)
