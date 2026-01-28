"""CAL Metrics Reporter"""

# standard library
from datetime import UTC, datetime
from functools import cached_property

# third-party
from requests import Response
from tcex import TcEx
from tcex.input.field_type import Sensitive
from tcex.requests_external import ExternalSession

# first-party
from core.json_db import JsonDB
from core.model.settings_model_base import SettingModelBase
from core.model.tie.task_setting_model import TaskSettingModel
from core.task.cal_auth import CALAuth
from core.task.task_abc import TaskABC


class MetricReporter(TaskABC):
    """Collect metrics from ExternalSession and post them to CAL."""

    def __init__(self, settings: SettingModelBase, tcex: TcEx, db: JsonDB):
        """Initialize class properties."""
        super().__init__(settings, tcex, db)
        self._cal_session: ExternalSession | None = None

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
    def session(self) -> ExternalSession:
        """Return the shared ExternalSession (writer of metrics)."""
        return self.tcex.session.external

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
        """Flush, snapshot, ship to CAL, then drop shipped lines."""
        try:
            # 1) Flush any buffered metrics to disk.
            self.session.metric_recorder.flush()

            # 2) Snapshot from recorder (expecting: (items, consumed_lines)).
            snapshot, lines = self.session.metric_recorder.file_snapshot()
            if not snapshot or not lines:
                self.log.debug('event=metrics-report, status=empty')
                return

            self.log.debug(
                f'event=metrics-report, action=send, items={len(snapshot)}, lines={lines}'
            )
            resp = self.send_to_cal(snapshot)

            # 3) On success, remove exactly the lines we read.
            if resp is None or resp.ok:
                self.session.metric_recorder.remove_x_lines(lines)
                self.log.info('event=metrics-report, status=success')
            else:
                self.log.error(
                    f'event=metrics-report, status=error, code={resp.status_code}, text={resp.text}'
                )
        except Exception:
            self.log.exception('event=metrics-report, status=exception')

    @cached_property
    def task_settings(self) -> TaskSettingModel:  # type: ignore
        """Static schedule/metadata for this reporter task."""
        return TaskSettingModel(
            description='Reports ExternalSession metrics to CAL.',
            max_execution_minutes=30,
            name='Metric Reporter',
            schedule_period=24,
            schedule_unit='hours',
        )
