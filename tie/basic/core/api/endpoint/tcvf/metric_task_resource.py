"""Class for /api/metric/task endpoint"""

import json
from datetime import UTC, datetime, timedelta
from functools import cached_property, lru_cache

from spectree import Response

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_metric
from core.json_db.dao import JsonDBDAO
from model import JobRequestModel


class MetricTaskResource(EndpointBase):
    """Class for /api/metric/task endpoint"""

    def _calculate_average(self, values: list[int]) -> int:
        """Calculate average."""
        try:
            if not values:
                return 0
            return round(sum(values) / len(values))
        except Exception:
            self.log.exception(f'values={values}')
            return 0

    def _calculate_timedelta_average(self, values: list[timedelta]) -> timedelta | None:
        """Calculate average."""
        try:
            if not values:
                return timedelta()
            return sum(values, timedelta()) / len(values)
        except Exception:
            self.log.exception(f'values={values}')
            return None

    @lru_cache(maxsize=1)  # noqa: B019
    def _generate_metrics(self, ttl_hash) -> dict:
        """Process metrics."""
        del ttl_hash
        self.log.trace('Generating metrics')
        jobs = list(self.dao.get_all())
        values = {
            'count_batch_group': [],
            'count_batch_indicator': [],
            'count_download_group': [],
            'count_download_indicator': [],
            'download_runtime': [],
            'convert_runtime': [],
            'upload_runtime': [],
            'total_runtime': [],
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

        return {
            'count_metrics': {
                # 'average_batch_group_count': self._calculate_average(values['count_batch_group']),
                # 'average_batch_indicator_count': self._calculate_average(
                #     values['count_batch_indicator']
                # ),
                # 'average_download_group_count': self._calculate_average(
                #     values['count_download_group']
                # ),
                # 'average_download_indicator_count': self._calculate_average(
                #     values['count_download_indicator']
                # ),
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
                'total_job_count': len(values['total_runtime']),
            },
            'uptime': datetime.now(UTC) - self.settings.date_started,
        }

    @cached_property
    def dao(self) -> JsonDBDAO[JobRequestModel]:
        """Return the dao."""
        return JsonDBDAO(self.db, JobRequestModel)

    @spec.validate(
        resp=Response('HTTP_200'),
        skip_validation=True,
        tags=[tag_metric],
    )
    def on_get(self, req: FalconRequest, resp: FalconResponse):  # noqa: ARG002
        """Get task metrics."""
        try:
            # generate metrics
            resp.text = json.dumps(self._generate_metrics(self._get_ttl_datetime()), default=str)
        except Exception:
            # TODO: @bsummers - update this
            import traceback  # noqa: PLC0415

            resp.text = traceback.format_exc()

    def _get_ttl_datetime(self) -> int:
        """Return the TTL datetime."""
        d = datetime.now(UTC)
        return int(d.replace(minute=d.minute // 10, second=0, microsecond=0).timestamp())
