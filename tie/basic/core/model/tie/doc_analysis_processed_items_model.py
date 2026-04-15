"""Model Definition"""

from pydantic import Field

from core.json_db import Index
from core.model.model_base import ModelBase


class DocAnalysisProcessedItemsModel(ModelBase):
    """Model Definition"""

    id: str = Index()
    items: dict = Field(
        default_factory=dict,
        description='Dictionary of processed items.',
    )

    @property
    def processed_groups(self) -> dict:
        """Return the processed groups."""
        return self.items.get('groups', {})

    @property
    def processed_indicators(self) -> dict:
        """Return the processed reports."""
        return self.items.get('reports', {})

    def last_time_processed(self, primary_type, secondary_type, uuid) -> None | int:
        """Return True if any groups have been processed."""
        primary_type = primary_type.lower()
        secondary_type = secondary_type.lower()
        if primary_type == 'indicators' and secondary_type == 'file':
            # we do not track files because we need more than just their value
            return None
        uuid = uuid.lower()
        return self.items.get(primary_type, {}).get(secondary_type, {}).get(uuid.lower())

    def track_processed(
        self, primary_type: str, secondary_type: str, uuid: str, timestamp: int
    ) -> None:
        """Track processed item."""
        primary_type = primary_type.lower()
        secondary_type = secondary_type.lower()
        if primary_type == 'indicators' and secondary_type == 'file':
            # we do not track files because we need more than just their value
            return
        uuid = uuid.lower()
        timestamp = int(timestamp)
        self.items.setdefault(primary_type, {}).setdefault(secondary_type, {})
        self.items[primary_type][secondary_type][uuid] = timestamp
