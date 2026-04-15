"""CAL Metrics Reporter (Redis-based)"""

from datetime import UTC, datetime
from functools import cached_property

from requests import Response
from tcex import TcEx
from tcex.input.field_type import Sensitive
from tcex.requests_external import ExternalSession
from tcex.requests_external.metrics_recorder_redis import MetricsRecorderRedis

from core.json_db import JsonDB
from core.model.settings_model_base import SettingModelBase
from core.model.tie.task_setting_model import TaskSettingModel
from core.task.cal_auth import CALAuth
from core.task.task_abc import TaskABC


class MetricReporterRedis(TaskABC):
    """Collect metrics from Redis and post them to CAL.

    This reporter reads metrics from a Redis list (queue) that was populated
    by MetricsRecorderRedis. It uses atomic RPOP operations to consume records,
    ensuring no race conditions or data loss.

    Flow:
    1. Pop a batch of records from Redis (atomic, removes them immediately)
    2. Send the batch to CAL
    3. On failure, records are lost (acceptable trade-off for simplicity)
       - Alternative: use a "processing" list pattern if at-least-once is required
    """

    # Maximum records to process per run
    BATCH_SIZE = 5000

    def __init__(self, settings: SettingModelBase, tcex: TcEx, db: JsonDB):
        """Initialize class properties."""
        super().__init__(settings, tcex, db)
        self._cal_session: ExternalSession | None = None
        self._metric_recorder: MetricsRecorderRedis | None = None

    def launch(self) -> None:
        """Spawn the task process."""
        self.process = self.process_metadata()
        self.process.start()
        self.log.info(f'task-event={self.task_settings.name}, pid={self.process.pid}')

    def launch_preflight_checks(self) -> None:
        """Run minimal preflight, then launch."""
        if self.tcex.app.ij.has_feature('CALSettings') is False:
            self.log.error('"CALSettings" feature is required to run MetricReporter task.')
        else:
            self.launch()

    @property
    def metric_recorder(self) -> MetricsRecorderRedis | None:
        """Return the MetricsRecorderRedis instance from the external session."""
        recorder = self.tcex.session.external.metric_recorder
        if recorder is None:
            return None
        if not isinstance(recorder, MetricsRecorderRedis):
            self.log.warning(
                'event=wrong-recorder-type, '
                f'expected=MetricsRecorderRedis, got={type(recorder).__name__}'
            )
            return None
        return recorder

    def construct_cal_session(self) -> ExternalSession:
        """Build a fresh ExternalSession pointed at CAL with valid auth."""
        self.log.debug('action=construct-session, message=constructing-new-session')
        new_session: ExternalSession = self.tcex.requests_external.get_session()
        new_session.log_curl = True
        new_session.base_url = self.settings.tc_cal_host

        # Acquire CAL token + expiry
        tc_cal = self.tc_cal()
        token = tc_cal['token']
        ts = tc_cal['timestamp']

        # Attach auth; log a short trace (avoid logging the token)
        new_session.auth = CALAuth(token.value, ts)
        self.log.debug(f'action=construct-session, valid_until={ts}')
        return new_session

    def tc_cal(self) -> dict[str, Sensitive | int]:
        """Fetch a CAL token (and expiry timestamp) from TC."""
        r = self.tcex.session.tc.post('/internal/token/cal', headers={'Accept': 'application/json'})
        payload = r.json()['data']
        return {'timestamp': payload['timestamp'], 'token': Sensitive(payload['token'])}

    @property
    def cal_session(self) -> ExternalSession:
        """Return a cached ExternalSession for CAL; refresh if token expired."""
        if not self._cal_session:
            self._cal_session = self.construct_cal_session()
        now = int(datetime.now(UTC).timestamp())
        # Refresh with 5s buffer if current token is stale
        if (now - 5) > self._cal_session.auth.timestamp:  # type: ignore[attr-defined]
            self._cal_session = self.construct_cal_session()
        return self._cal_session

    def send_to_cal(self, data: list) -> Response:
        """POST metrics batch to CAL analyze endpoint."""
        return self.cal_session.post('/helix/appmetrics/v1/send', json=data)

    def run(self) -> None:
        """Pop records from Redis and ship to CAL.

        Records are atomically removed from Redis when popped. If the CAL
        request fails, those records are lost. This is an acceptable trade-off
        for simplicity - metrics are non-critical telemetry data.
        """
        try:
            recorder = self.metric_recorder
            if recorder is None:
                self.log.debug('event=metrics-report, status=no-recorder')
                return

            # Check queue size first
            queue_len = recorder.queue_length()
            if queue_len == 0:
                self.log.debug('event=metrics-report, status=empty')
                return

            # Pop records atomically (this removes them from Redis)
            records = recorder.pop_records(self.BATCH_SIZE)
            if not records:
                self.log.debug('event=metrics-report, status=empty-after-pop')
                return

            self.log.debug(
                f'event=metrics-report, action=send, '
                f'items={len(records)}, queue_remaining={queue_len - len(records)}'
            )

            resp = self.send_to_cal(records)

            if resp is None or resp.ok:
                self.log.info(f'event=metrics-report, status=success, sent={len(records)}')
            else:
                self.log.error(
                    f'event=metrics-report, status=error, code={resp.status_code}, text={resp.text}'
                )
                # --- OPTIONAL: Re-queue failed records ---
                # Records are pushed to the tail so they'll be processed first
                # on the next run (preserves FIFO order).
                # WARNING: Could cause infinite retry loop if CAL is persistently down.
                # Consider adding retry count tracking or a dead-letter queue for production.
                #
                # requeued = recorder.push_records(records)
                # self.log.warning(
                #     f'event=metrics-report, action=requeue, requeued={requeued}'
                # )
        except Exception:
            self.log.exception('event=metrics-report, status=exception')

    @cached_property
    def task_settings(self) -> TaskSettingModel:  # type: ignore
        """Static schedule/metadata for this reporter task."""
        return TaskSettingModel(
            description='Reports ExternalSession metrics to CAL (Redis-backed).',
            max_execution_minutes=30,
            name='Metric Reporter (Redis)',
            schedule_period=30,
            schedule_unit='seconds',
        )
