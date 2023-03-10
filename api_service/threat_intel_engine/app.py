"""ThreatConnect Feed API Service App"""
# standard library
from time import sleep, time
from typing import TYPE_CHECKING

# third-party
import schedule
from api import (
    JobRequestResource,
    JobSettingResource,
    MetricProcessingResource,
    MetricTaskResource,
    ReportBatchErrorResource,
    SupportLogSearchResource,
    TaskResource,
    TaskStatusResource,
)
from api.middleware import InjectablesMiddleware
from api_service_falcon import ApiServiceFalcon
from model import SettingsModel
from more import initialize_db
from tasks import (
    Cleaner,
    ConvertPathPipe,
    DownloadPathPipe,
    ScheduleNextDownload,
    Tasks,
    UploadPathPipe,
)
from tcex.backports import cached_property
from tcex.exit import ExitCode
from tcex.sessions.auth.hmac_auth import HmacAuth
from tcex.sessions.tc_session import TcSession

if TYPE_CHECKING:
    # standard library

    # third-party
    from tcex.input.field_types import Sensitive

    # first-party
    from app_inputs import AppBaseModel


class App(ApiServiceFalcon):
    """API Service App"""

    def __init__(self, _tcex):
        """Initialize class properties."""
        super().__init__(_tcex)

        # properties
        self.tasks = Tasks()

        #
        # Define Tasks
        #

        # ┌─────────────┐          ┌─────────────┐          ┌─────────────┐
        # │ Download    │          │ Convert     │          │ Upload      │
        # │             ├─────────►│             ├─────────►│             │
        # │             │          │             │          │             │
        # └─────────────┘          └─────────────┘          └─────────────┘

        # add tasks in order of flow
        self.tasks.add_task_path_pipe(
            [
                DownloadPathPipe(self.settings, self.tcex, self.provider_sdk),
                ConvertPathPipe(self.settings, self.tcex),
                UploadPathPipe(self.settings, self.tcex),
            ]
        )

        # standalone tasks
        self.tasks.add_task(Cleaner(self.settings, self.tcex, self.tasks))

        # schedule next download
        self.tasks.add_task(ScheduleNextDownload(self.settings, self.tcex))

        # initialize the db
        self._initialize_db()

    def build_falcon_app(self):
        """Construct a new falcon app."""
        app = super().build_falcon_app()
        #
        # Add APP middleware and routes
        #

        app.add_middleware(
            InjectablesMiddleware(
                provider_sdk=self.provider_sdk,
                settings=self.settings,
                tasks=self.tasks,
            )
        )

        #
        # Add Routes
        #

        app.add_route('/api/job/request', JobRequestResource())
        app.add_route('/api/job/setting', JobSettingResource())
        app.add_route('/api/metric/processing', MetricProcessingResource())
        app.add_route('/api/metric/task', MetricTaskResource())
        app.add_route('/api/report/batch-error', ReportBatchErrorResource())
        # self.app.add_route('/api/report/pdf-tracker', ReportPdfTrackerResource())
        app.add_route('/api/support/log-search', SupportLogSearchResource())
        app.add_route('/api/task', TaskResource())
        app.add_route('/api/task/{task_name}', TaskResource())
        app.add_route('/api/task/status', TaskStatusResource())
        return app

    @staticmethod
    def _initialize_db():
        """Initialize database and perform any DB cleanup that needs to be done on restart."""
        initialize_db()

    def _preflight_check(self):
        """Perform preflight check."""
        # perform preflight check on external API
        self._preflight_check_external_api()

        # perform preflight check on filesystem
        self._preflight_check_filesystem()

        # perform preflight check on ThreatConnect API
        self._preflight_check_tc_api()

    def _preflight_check_external_api(self):
        """Perform preflight check for external API."""
        try:
            # get_all returns a generator, so make sure we consume it to know if it fails or not.
            list(
                self.provider_sdk.get_all(
                    tql='typeName EQ "Email Address"', owner=self.inputs.model.external_tc_owner
                )
            )
        except Exception as ex:
            self.log.error(f'event=preflight-check-cs-api-failed, error={ex}')
            raise RuntimeError('Preflight check for CS API failed.') from ex

    def _preflight_check_filesystem(self):
        """Perform preflight check."""
        preflight_check_file = self.settings.base_path / 'preflight'

        try:
            preflight_check_file = self.settings.base_path / 'preflight'
            preflight_check_file.write_text('preflight check')
            self.log.info(f'event=preflight-check-filesystem, file={preflight_check_file}')
        except Exception as ex:
            self.log.error(
                f'event=preflight-check-filesystem-failed, file={preflight_check_file}, error={ex}'
            )
            raise RuntimeError('Preflight check for filesystem failed.') from ex

    def _preflight_check_tc_api(self):
        """Perform preflight check."""
        try:
            owners = self.tcex.api.tc.v3.security.owners()
            owners = [o.model.name for o in owners]
            self.log.info(f'event=preflight-check-cs, owners={owners}')
        except Exception as ex:
            self.log.error(f'event=preflight-check-tc-api-failed, error={ex}')
            raise RuntimeError('Preflight check for TC API failed.') from ex

    @cached_property
    def provider_sdk(self):
        """Return the Stub SDK.

        Typically this method would return the actual SDK for the provider. This is only for
        demonstration purposes.
        """

        model: 'AppBaseModel' = self.inputs.model

        class ProviderSdk:
            """Provider SDK class."""

            def __init__(self, tc_url: str, access_id: str, secret_key: 'Sensitive', log):
                self.tc_session = TcSession(HmacAuth(access_id, secret_key), tc_url)
                self.log = log

            def get_all(self, tql: str, owner: str):
                """Return a generator of indicators."""
                limit = 1000
                offset = 0
                while True:
                    response = self.tc_session.get(
                        '/v3/indicators',
                        params={
                            'tql': tql,
                            'owner': owner,
                            'resultLimit': limit,
                            'resultStart': offset,
                        },
                    )
                    offset += limit
                    response.raise_for_status()
                    data = response.json().get('data')
                    self.log.warning(f'data={data}')
                    if data:
                        yield from data
                    else:
                        return

            def get(self, indicator: str):
                """Return a single indicator."""
                return self.tc_session.get(f'/v3/indicators/{indicator}').json()

        return ProviderSdk(
            model.external_tc_url,
            model.external_tc_api_access_id,
            model.external_tc_api_secret_key,
            self.log,
        )

    def loop_forever(self):
        """Loop forever running scheduled task as appropriate."""
        self._preflight_check()

        while True:
            schedule.run_pending()
            sleep(1)  # wake up often to catch shutdown

            # handle cleanup and shutdown
            if self.tcex.service.message_broker.shutdown is True:
                self.tcex.log.trace('action=loop-forever, shutdown=True')
                max_wait = 30
                deadline = time() + max_wait

                # wait for up to "max_wait"
                self.tcex.log.trace(
                    f'action=loop-forever-wait-for-task-completion, max-seconds={max_wait}'
                )
                while True:
                    # allow processes to wrap up current work before exiting App
                    # TODO: @cblades is the or logic here backwards?
                    # if time() > deadline or len(self.tasks.alive()) > 0:
                    if time() > deadline or len(self.tasks.alive()) == 0:
                        break
                    sleep(1)

                # kill processes
                self.tasks.kill_all()

                break

        self.tcex.exit(ExitCode.SUCCESS, 'App has been successfully stopped')

    @cached_property
    def settings(self):
        """Return settings"""

        return SettingsModel(
            owner=self.inputs.model.tc_owner,
            base_path=self.inputs.model.tc_out_path,
            external_owner=self.inputs.model.external_tc_owner,
            tql=self.inputs.model.tql,
        )
