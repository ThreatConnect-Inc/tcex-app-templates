"""Class for /api/metric/task endpoint"""
# standard library
import json
from datetime import timedelta
from typing import List, Optional

# third-party
import arrow
import falcon
from sqlalchemy.orm import Query

# first-party
from schema import JobRequestSchema

from .resource_abc import ResourceABC


# pylint: disable=unused-argument
class MetricTaskResource(ResourceABC):
    """Class for /api/metric/task endpoint"""

    def _db_query_get(self) -> Query:
        """Return DB query."""
        return self.session.query(JobRequestSchema)

    def _db_result_get(self, query: Query) -> List[JobRequestSchema]:
        """Return DB records."""
        return self._db_get_record(
            query, 'all', 'Unexpected error occurred while retrieving metrics.'
        )

    def _calculate_average(self, values: List[int]) -> Optional[float]:
        """Calculate average."""
        try:
            if not values:
                return 0
            return sum(values) / len(values)
        except Exception:
            self.log.error(f'values={values}')
            return None

    def _calculate_timedelta_average(self, values: List[timedelta]) -> Optional[timedelta]:
        """Calculate average."""
        try:
            if not values:
                return timedelta()
            return sum(values, timedelta()) / len(values)
        except Exception:
            self.log.error(f'values={values}')
            return None

    def _generate_metrics(self, jobs: List[JobRequestSchema]) -> dict:
        """Process metrics."""
        values = {
            'count_batch_group': [],
            'count_batch_indicator': [],
            'count_download_group': [],
            'count_download_indicator': [],
            'download_runtime': [],
            'convert_runtime': [],
            'upload_runtime': [],
            'total_runtime': [],
            'total_job_count': 0,
        }
        for job in jobs:
            values['count_batch_group'].append(job.count_batch_group_success)
            values['count_batch_indicator'].append(job.count_batch_indicator_success)
            values['count_download_group'].append(job.count_download_group)
            values['count_download_indicator'].append(job.count_download_indicator)
            if job.download_runtime is not None:
                values['download_runtime'].append(job.download_runtime)
            if job.convert_runtime is not None:
                values['convert_runtime'].append(job.convert_runtime)
            if job.upload_runtime is not None:
                values['upload_runtime'].append(job.upload_runtime)
            if job.total_runtime is not None:
                values['total_runtime'].append(job.total_runtime)
            values['total_job_count'] += 1

        return {
            'count_metrics': {
                'total_count_batch_group': sum(values['count_batch_group']),
                'total_count_batch_indicator': sum(values['count_batch_indicator']),
                'total_count_download_group': sum(values['count_download_group']),
                'total_count_download_indicator': sum(values['count_download_indicator']),
            },
            'runtime_metrics': {
                'average_download_runtime': self._calculate_timedelta_average(
                    values['download_runtime']
                ),
                'average_convert_runtime': self._calculate_timedelta_average(
                    values['convert_runtime']
                ),
                'average_upload_runtime': self._calculate_timedelta_average(
                    values['upload_runtime']
                ),
                'average_total_runtime': self._calculate_timedelta_average(values['total_runtime']),
                'max_download_runtime': max(values['download_runtime'], default=timedelta()),
                'max_convert_runtime': max(values['convert_runtime'], default=timedelta()),
                'max_upload_runtime': max(values['upload_runtime'], default=timedelta()),
                'max_total_runtime': max(values['total_runtime'], default=timedelta()),
                'total_download_time': sum(values['download_runtime'], timedelta()),
                'total_convert_time': sum(values['convert_runtime'], timedelta()),
                'total_upload_time': sum(values['upload_runtime'], timedelta()),
                'total_time': sum(values['total_runtime'], timedelta()),
                'total_download_job_count': len(values['download_runtime']),
                'total_convert_job_count': len(values['convert_runtime']),
                'total_upload_job_count': len(values['upload_runtime']),
            },
            'uptime': arrow.utcnow() - self.settings.date_started,
        }

    def on_get(self, req: falcon.Request, resp: falcon.Response):
        """Handle GET requests."""
        query = self._db_query_get()
        jobs = self._db_result_get(query)

        # generate metrics
        resp.text = json.dumps(self._generate_metrics(jobs), default=str)
