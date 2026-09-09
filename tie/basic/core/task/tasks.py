"""Tasks Container"""

import logging
import os
import signal
import time
import traceback
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, ClassVar

import arrow
import schedule
from tcex import TcEx
from tcex.exit import ExitCode

from core.beacon import inject
from core.dao.job_dao import JobRequestDAO
from core.json_db import JsonDB
from core.model.onboarding_model import is_onboarding_complete
from core.model.settings_model_base import SettingModelBase
from core.service.notification_helper import NotificationHelper
from core.service.notification_service import NOTIFICATION_BY_CATEGORY
from core.supervisor import Supervisor
from model.job_request_model import JobRequestModel

if TYPE_CHECKING:
    from task import TaskABC

logger = logging.getLogger('tcex')


class Tasks:
    """Tasks Container"""

    status_final: ClassVar[list[str]] = []

    def __init__(
        self,
        tcex: TcEx,
        db: JsonDB = inject(JsonDB),
        settings: SettingModelBase = inject(SettingModelBase),
    ):
        """Initialize class properties.

        Args:
            tcex: TcEx instance.
            db: JsonDB instance for persisting Supervisor state.
            settings: Application settings.
        """
        # properties
        self._tasks = set()
        self.log = logger
        self.tcex = tcex
        self.exit_service = tcex.exit
        self.settings = settings
        self.db = db

        # The URL this app is actually served at, learned from the first request to arrive
        # (api_service_falcon_abc._record_app_base_url). None until then — a background
        # task has no request of its own to read it from. See _onboarding_link.
        self.app_base_url: str | None = None

        # Create JobRequestDAO for Supervisor
        self.job_dao = JobRequestDAO(db, settings)

        # Initialize Supervisor with JsonDB, job_dao, settings, and exit service
        self.supervisor = Supervisor(
            db=db,
            job_dao=self.job_dao,
            settings=settings,
            exit_service=self.exit_service,
        )

        # Notification state tracking (disabled when notification_digest_interval is None).
        # Read live via the property below — see its docstring.
        self.notification_helper = NotificationHelper(settings, tcex, db)
        self.last_digest_time = datetime.now(UTC)
        # Own timer, not last_digest_time — that never advances with notifications off.
        # None until a reminder actually sends, which is what makes the watchdog retry.
        self.last_setup_reminder_time: datetime | None = None
        self.reported_retrying: set[str] = set()  # job IDs already reported as retrying
        self.reported_resolved: set[str] = set()  # job IDs already reported as perm_fail/recovered

        # Check for stale pipelines and enter probation mode if needed
        # Stale pipelines: first job must succeed or app shuts down
        # Healthy pipelines: baseline is reset normally
        self.supervisor.check_and_enter_probation()

        # Built lazily after tasks are registered via add_task_path_pipe
        self._status_reset_mapping: dict[str, str] | None = None

        # schedule watchdog for tasks
        schedule.every(1).minute.do(self.watchdog)

    @property
    def notifications_enabled(self) -> bool:
        """Whether notifications are on, resolved live on every read.

        `PUT /api/settings` rebinds `settings.app_settings`, so this must not be cached on
        `Tasks` (a singleton built once at boot). A cached value fails both ways: enabling
        notifications through the UI would never take effect until restart, and disabling
        them would leave this True while `notification_digest_interval` is None, which
        `watchdog` then compares a timedelta against. Same reasoning as
        `Scheduler.frequency` and `Cleaner.max_batch_errors`.
        """
        return self.settings.app_settings.notification_digest_interval is not None

    def send_startup_notification(self) -> None:
        """Send startup notification. Call after preflight checks pass."""
        if self.notifications_enabled:
            notification_config = NOTIFICATION_BY_CATEGORY['app_startup']
            notification_types = self.settings.app_settings.notification_types or []
            self.notification_helper.notify(
                notification_config,
                send_now='app_startup' in notification_types,
            )
        self._maybe_send_setup_required_reminder()

    def send_preflight_failure_notification(self, reason: str) -> None:
        """Send a notification when preflight checks fail."""
        if self.notifications_enabled:
            notification_config = NOTIFICATION_BY_CATEGORY['app_startup_failed']
            self.notification_helper.notify(
                notification_config,
                send_now=True,
                reason=reason,
            )

    def add_task(self, task: 'TaskABC'):
        """Add a task to the container."""
        self._tasks.add(task)
        task.schedule()

    def add_task_path_pipe(self, tasks: 'list[TaskABC]'):
        """Add a task to the container."""
        for index, task in enumerate(tasks):  # reverse list
            # set the task index
            task.task_settings.index = index

            # first task in pipe
            if index == 0:
                task.task_settings.pipe_task_start = True
            else:
                # set previous task name for pipe, unless first task in pipe
                task.task_settings.previous_task_name = tasks[index - 1].task_settings.name

            # last task in pipe
            if index == len(tasks) - 1:
                task.task_settings.pipe_task_complete = True

                # for last task in pipe, set the pipe task complete to True
                task.task_settings.working_dir_out = (
                    task.task_settings.base_path / 'done_working_dir'
                )
                task.task_settings.working_dir_out.mkdir(parents=True, exist_ok=True)

                # add final status
                Tasks.status_final.append(task.task_settings.status_complete)
            else:
                # out directory for the current task is the "in" directory for
                # the next task, except when on the last task in the pipe
                task.task_settings.working_dir_out = tasks[index + 1].task_settings.working_dir_in

            self.log.debug(
                f'pipe-event=add-task-pipe, task-name={task.task_settings.name}, '
                f'pipe-task-start={task.task_settings.pipe_task_start}, '
                f'pipe-task-complete={task.task_settings.pipe_task_complete}, '
                f'previous-task-name={task.task_settings.previous_task_name}, '
                f'working-dir-out={task.task_settings.working_dir_out}'
            )
            self.add_task(task)

    def all(self) -> 'list[TaskABC]':
        """Return all processes that are alive."""
        return list(self._tasks)

    def alive(self) -> 'list[TaskABC]':
        """Return all processes that are alive."""
        return [t for t in self._tasks if t.process is not None and t.process.is_alive()]

    def kill(self, task: 'TaskABC'):
        """Kill multi-processes to cleanly exit app."""
        self.log.warning(f'event=kill-task, task-name={task.task_settings.name}')
        if task.process is not None:
            if task.process.is_alive():
                try:
                    self._send_signal_to_task(signal.SIGALRM, task)
                    time.sleep(2)
                    self._send_signal_to_task(signal.SIGKILL, task)
                except Exception:
                    self.log.warning(f'event=kill-task-failed, pid={task.process.pid}')
                    self.log.warning(traceback.format_exc())

            task.process.join(10)

    def kill_all(self):
        """Kill all multi-process."""
        max_wait = 30
        deadline = time.time() + max_wait

        # wait for up to "max_wait"
        self.log.trace(f'action=kill_all-wait-for-task-completion, max-seconds={max_wait}')
        while True:
            # allow processes to wrap up current work before exiting App
            if time.time() > deadline or len(self.alive()) == 0:
                break
            time.sleep(1)
        for task in self.all():
            self.kill(task)

    def watchdog(self) -> None:  # noqa: C901
        """Monitor tasks and perform health checks.

        Per-job backoff is handled directly on JobRequestModel fields.
        Pipeline staleness is checked by Supervisor.tick() using job completion times.
        """
        self.log.debug(f'task-event=run-watchdog, task-count={len(self._tasks)}')
        api_limit: None | dict = None

        # Run Supervisor tick for pipeline health monitoring
        # This checks if any pipeline has no completed jobs for threshold (default 48h)
        self.supervisor.tick()

        # Check for shutdown request from Supervisor (staleness detected in main process)
        if self.supervisor.shutdown_requested:
            self.log.warning(
                f'task-event=supervisor-shutdown-requested, '
                f'reason={self.supervisor.shutdown_reason}'
            )
            self._graceful_shutdown(self.supervisor.shutdown_reason)
            return

        # Check for unrecoverable failure from forked tasks (cross-process via Redis)
        for task in self.all():
            if task.ns.unrecoverable_failure is True:
                self.log.warning(
                    f'task-event=unrecoverable-failure, task-name={task.task_settings.name}'
                )
                self._graceful_shutdown('Task reported unrecoverable failure')
                return

        for task in self.all():
            # see if we should kill the task as its over its time limit
            if task.process is not None and task.process.is_alive():
                # update date expires based on heartbeat
                self.log.trace(
                    f'task-event=watchdog, '
                    f'heartbeat-value={task.ns.heartbeat}, task={task.task_settings.name}'
                )

                if task.ns.heartbeat is not None and arrow.now(UTC) - task.ns.heartbeat > timedelta(
                    minutes=task.task_settings.max_execution_minutes
                ):
                    self.log.warning(
                        f'task-event=kill-task, task-name={task.task_settings.name}, '
                        f'process-id={task.process.pid}, '
                        f'metadata={task.process.metadata.dict()}, '
                    )
                    self.kill(task)
                    if task.process.is_alive():
                        # kill() has already done SIGALRM -> SIGKILL -> join(10). A child
                        # still alive here is in uninterruptible I/O and will exit shortly.
                        # is_alive() is unreliable at this point, so it must NOT gate
                        # cleanup: by the next tick the process is reaped and the outer
                        # guard skips this block for good, leaving the job stuck
                        # "In Progress" and relaunching forever.
                        self.log.warning(
                            f'task-event=timeout-process-still-alive, '
                            f'task-name={task.task_settings.name}, '
                            f'process-id={task.process.pid}'
                        )
                    task.on_timeout()

                # Handle setting our api limit hit metric since its forked
                # We only care about the value for the DownloadPathPipe task
                if type(task).__name__ in ['Download']:
                    self.log.debug(f'Task: {type(task).__name__} has: {task.ns.api_limit_details}')
                    # Set to latest value
                    if api_limit is None or task.ns.api_limit_details.get(
                        'date_set'
                    ) > api_limit.get('date_set'):
                        api_limit = task.ns.api_limit_details

            if api_limit is not None:
                # self.tcex.app.service.add_metric(
                #     'Vulnerability API Limit Hit', api_limit.get('reached')
                # )
                self.log.debug(f'API Limit Hit: {api_limit.get("reached")}')

        # Check if digest interval has elapsed and send digest if needed.
        # Read the interval ONCE: `PUT /api/settings` can rebind app_settings between a
        # `notifications_enabled` check and a separate re-read, which would pair True with
        # a None interval and raise TypeError on the comparison below — inside
        # `schedule.run_pending()`, which `loop_forever` does not guard, killing the
        # watchdog, the supervisor tick and every task tick with it.
        digest_interval = self.settings.app_settings.notification_digest_interval
        if digest_interval is not None:
            now = datetime.now(UTC)
            elapsed = now - self.last_digest_time
            if elapsed >= digest_interval:
                self._send_digest(now)

        # Every tick, not just when the digest fires — it has to keep retrying until a
        # request arrives and reveals app_base_url.
        self._send_setup_reminder_if_due()

    def pause_all(self):
        """Pause all tasks.

        Sets pause flag in Tasks' settings so that it will not persist across restart.
        """
        for task in self.all():
            task.task_settings.paused = True

    def _graceful_shutdown(self, reason: str) -> None:
        """Perform graceful shutdown: pause tasks, kill running, then exit.

        Tier 1 notification: always sent, never filtered.

        Args:
            reason: Human-readable reason for shutdown.
        """
        self.log.error(f'task-event=graceful-shutdown-initiated, reason={reason}')

        # Send shutdown notification immediately (always sent, not user-configurable)
        if self.notifications_enabled:
            notification_config = NOTIFICATION_BY_CATEGORY['app_shutdown']
            self.notification_helper.notify(
                notification_config,
                send_now=True,
                reason=reason[:80],
            )

        self.pause_all()
        self.kill_all()
        if self.exit_service:
            self.exit_service.exit(ExitCode.FAILURE, f'Shutting down: {reason}')

    def _is_newly_perm_failed(self, job, status_failed: str) -> bool:
        return (
            job.status.casefold() == status_failed
            and job.request_id not in self.reported_resolved
            and job.date_failed is not None
            and job.date_failed >= self.last_digest_time
        )

    def _sweep_job_state(self) -> tuple[list, list, list]:
        """Classify jobs into retrying, permanently failed, and recovered buckets.

        Scans all jobs because the recovered/perm-failed checks depend on the
        reported_retrying/reported_resolved tracking sets, not just timestamps.
        """
        retrying = []
        perm_failed = []
        recovered = []

        status_failed = self.settings.job.status_failed

        for job in self.db.load_all(JobRequestModel):
            job_id = job.request_id

            # Retrying: has failures, still pending (not permanently failed), not yet reported
            if (
                job.failure_count > 0
                and job.status.casefold() != status_failed
                and job_id not in self.reported_retrying
            ):
                if job.date_failed is not None and job.date_failed >= self.last_digest_time:
                    retrying.append(job)

            elif self._is_newly_perm_failed(job, status_failed):
                perm_failed.append(job)

            # Recovered: completed, was previously reported as retrying, not yet resolved
            elif (
                job.date_completed is not None
                and job_id in self.reported_retrying
                and job_id not in self.reported_resolved
            ):
                # Self-heal omission: if first failure and completion both in this window, skip
                if job.date_failed is not None and job.date_failed >= self.last_digest_time:
                    continue
                recovered.append(job)

        return retrying, perm_failed, recovered

    def _send_digest(self, now: datetime) -> None:
        """Send a digest notification if anything noteworthy happened.

        Tier 2: periodic digest batched into fixed windows. Each job appears in at most
        2 digests (retrying + resolution). Self-healed jobs are omitted.
        """
        self.log.debug(
            f'task-event=digest-start, last_digest_time={self.last_digest_time.isoformat()}'
        )

        retrying, perm_failed, recovered = self._sweep_job_state()

        if not retrying and not perm_failed and not recovered:
            self.log.debug('task-event=digest-sweep, result=nothing-to-report')
            self.last_digest_time = now
            return

        self.log.info(
            f'task-event=digest-sweep, '
            f'retrying={len(retrying)}, perm_failed={len(perm_failed)}, '
            f'recovered={len(recovered)}'
        )

        notification_types = self.settings.app_settings.notification_types or []

        digest_buckets = [
            ('job_retrying', retrying, self.reported_retrying),
            ('job_failed', perm_failed, self.reported_resolved),
            ('job_recovered', recovered, self.reported_resolved),
        ]

        for category, jobs, tracking_set in digest_buckets:
            if not jobs:
                continue
            notification_config = NOTIFICATION_BY_CATEGORY[category]
            ids = [j.request_id for j in jobs]
            self.notification_helper.notify(
                notification_config,
                send_now=category in notification_types,
                job_ids=ids,
                count=len(jobs),
            )
            tracking_set.update(ids)

        self.last_digest_time = now

    def _maybe_send_setup_required_reminder(self) -> None:
        """Send a 'finish setup' reminder while onboarding is incomplete.

        Silent when notifications are disabled — that usually means the TC instance does
        not support them, so there is nowhere to send. Bypasses only the per-category
        opt-in, by passing a config OBJECT to notify(): 'Setup Required' is not one of the
        categories an admin can select, so it would never be opted into.

        Onboarding is checked live on every call — Tasks is a long-lived singleton built
        once at boot — so the reminder stops itself once setup completes.

        Sends with a link when `app_base_url` is known and without one when it is not.
        Measured on the platform: nothing reaches the app's HTTP surface until a human
        opens the UI, so waiting for a link meant an unconfigured app sat silent
        indefinitely. A guessed URL is still never sent — see `_onboarding_link`.
        """
        if not self.notifications_enabled:
            return
        if is_onboarding_complete(self.db):
            return

        try:
            self._send_setup_required_reminder()
        except Exception:
            # A reminder must never take the app down. Both callers run inside
            # `schedule.run_pending()` (watchdog) or app startup, and run_pending does not
            # guard its jobs — an exception here would kill the watchdog, the supervisor
            # tick and every task tick with it. The HTTP layer is already safe
            # (`NotificationService.send` never raises), but `notify()` above it still can:
            # `message_template.format()` raises KeyError on a missing placeholder, there is
            # an explicit `raise ValueError` when no template and no message are supplied,
            # and the NotificationModel build plus DB write can both fail.
            self.log.exception('action=setup-required-reminder, status=failed')

    def _send_setup_required_reminder(self) -> None:
        """Build and send the reminder. See `_maybe_send_setup_required_reminder`."""
        notification_config = NOTIFICATION_BY_CATEGORY['setup_required']
        if self.app_base_url:
            link = self._onboarding_link()
            send_kwargs = {'link': link}
            detail = link
        else:
            # The template hardcodes <a href="{link}">, so format() would KeyError.
            # Clearing it lets notify() use the message= override. Category and priority
            # are untouched, so it still files and filters the same in the UI.
            notification_config = notification_config._replace(message_template=None)
            send_kwargs = {
                'message': (
                    'Setup is incomplete — no ingestion will run until it is finished. '
                    'Open this service in ThreatConnect and complete setup on the '
                    'Settings page.'
                )
            }
            detail = 'no-link'

        self.last_setup_reminder_time = datetime.now(UTC)
        self.notification_helper.notify(notification_config, send_now=True, **send_kwargs)
        self.log.info(f'action=setup-required-reminder, status=sent, link={detail}')

    def _send_setup_reminder_if_due(self) -> None:
        """Send the setup-required reminder if the digest interval has elapsed.

        `last_setup_reminder_time` is None until something sends, so with no URL yet this is
        due every watchdog tick — a retry once a minute. After the first send it settles
        onto the digest interval.
        """
        interval = self.settings.app_settings.notification_digest_interval
        if interval is None:
            return
        last_reminder = self.last_setup_reminder_time
        if last_reminder is None or datetime.now(UTC) - last_reminder >= interval:
            self._maybe_send_setup_required_reminder()

    def _onboarding_link(self) -> str:
        """Return a URL to this app's Settings page, where setup is started.

        The ONLY source is the address the platform actually served a request to, captured
        from the `request_url` the service message carries (see
        `api_service_falcon_abc._record_app_base_url`). This is the same thing the TAXII
        service app does — it builds every discovery URL from `request_url` and never
        reconstructs one (`api/endpoint/taxii/resources/taxii_resource.py`,
        `services/taxii_service.py`).

        Do NOT reconstruct this from `tc_api_path` + `displayPath` + package version. It
        looks plausible and is always wrong for a deployed service. `displayPath` comes
        from install.json and is App-level, so it yields '/services/my_app/v1'; the
        platform actually serves the app at '/services/my_app_<instance>/v1', where
        `<instance>` is assigned per deployment. That suffix appears nowhere in install.json
        or in the startup inputs (`tc_svc_id` is an unrelated integer) — `request_url` is
        the only place it exists. A reconstructed link 404s.

        Callers must check `app_base_url` before calling; this raises rather than guess.

        NO TRAILING SLASH after `settings`, and this matters. `ui/src/index.html` carries a
        relative `<base href="./">`, so a trailing slash makes the browser resolve every
        bundle against `.../settings/` — and the Falcon static route answers an unmatched
        path with `fallback_filename='index.html'` at HTTP 200. The browser then gets HTML
        where JavaScript was expected: a blank page, no console error, no server error.
        (`falcon_app.py`'s `strip_url_path_trailing_slash` normalises the SERVER's view of
        the path only; it does not change what `<base>` resolves against.)
        """
        if not self.app_base_url:
            ex_msg = '_onboarding_link called before app_base_url was recorded'
            raise RuntimeError(ex_msg)
        return f'{self.app_base_url}/settings'

    @property
    def status_reset_mapping(self) -> dict[str, str]:
        """Return mapping of active status -> previous stage's complete status."""
        if self._status_reset_mapping is None:
            mapping: dict[str, str] = {}
            for task in self.all():
                ts = task.task_settings
                previous_task_name = getattr(ts, 'previous_task_name', None)
                if previous_task_name is not None:
                    previous_status_complete = f'{previous_task_name.lower()} complete'
                    mapping[ts.status_active.casefold()] = previous_status_complete
            self._status_reset_mapping = mapping
        return self._status_reset_mapping

    def _send_signal_to_task(self, send_signal: signal.Signals, to_task: 'TaskABC'):
        """Send signal to task."""
        if to_task.process is None or not to_task.process.is_alive():
            self.log.warning(
                f'event=send-signal-to-task-failed, task-name={to_task.task_settings.name}, '
                f'reason=task-not-running'
            )
            return
        self.log.trace(
            f'event=send-signal-to-task, signal={send_signal}, '
            f'task-name={to_task.task_settings.name}, pid={to_task.process.pid}'
        )
        os.kill(to_task.process.pid, send_signal)
