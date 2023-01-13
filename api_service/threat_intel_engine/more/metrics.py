"""Metrics Module"""
# first-party
from more import DbUtil, session
from schema import TiProcessingMetricSchema


class Metrics:
    """Metrics Module"""

    def __init__(self):
        """Initialize class properties."""

        # properties
        self.db = DbUtil()
        self.session = session

    def get_metrics(self, metric_name: str) -> TiProcessingMetricSchema:
        """Return metrics."""
        query = self.session.query(TiProcessingMetricSchema).filter(
            TiProcessingMetricSchema.ti_type == metric_name
        )
        return self.db.get_record(query, 'one_or_none', 'Unexpected error getting metric.')

    def process_metric(self, metric_name: str, metric_value: int):
        """Add or update metrics."""
        metric = self.get_metrics(metric_name)
        if metric is None:
            metric = self.db.create_record(
                TiProcessingMetricSchema,
                {
                    'ti_type': metric_name,
                    'ti_count': metric_value,
                },
                'Unexpected error creating TI Processing Metric.',
            )
            self.db.add_record(
                self.session, metric, 'Unexpected error adding TI Processing Metric.'
            )
        else:
            metric.ti_count += metric_value
            self.db.patch_record(self.session, metric, 'Unexpected failure updating metric.')
