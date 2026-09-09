"""Scheduled Task"""

import datetime
from abc import abstractmethod
from collections.abc import Callable
from typing import NamedTuple

from tcex import TcEx
from tcex.api.tc.v3.groups.group import Group, Groups
from tcex.api.tc.v3.tql.tql_operator import TqlOperator
from tcex.pleb.cached_property import cached_property

from core.dao.report_pdf_tracker_dao import ReportPdfTrackerDAO
from core.json_db import JsonDB
from core.model.tie.report_pdf_tracker_model import ReportPdfTrackerModel
from core.model.tie.task_setting_model import TaskSettingModel
from core.task.task_abc import TaskABC
from model import SettingModel


class DocumentRetrievalError(Exception):
    """Exception raised when document retrieval from an external server fails."""

    def __init__(
        self,
        message='Failed to retrieve the document from the external server.',
        status_code=None,
        url=None,
    ):
        """Initialize the exception."""
        self.message = message
        self.status_code = status_code
        self.url = url
        super().__init__(self.__str__())

    def __str__(self):
        """Representation of the exception."""
        details = f'{self.message}'
        if self.status_code is not None:
            details += f' HTTP Status Code: {self.status_code}.'
        if self.url:
            details += f' URL: {self.url}.'
        return details


class TaskSettingCustomModel(TaskSettingModel):
    """Custom model for cleaner task settings."""

    pending_tag: str
    max_attempts: int
    #: Once a group is past `max_attempts`, `run()` skips it entirely except for retrying
    #: the tag removal itself — paced off the group's own `date_added` rather than anything
    #: persisted, so this needs no state, just how often (in seconds) to check back.
    retry_remove_tag_interval_seconds: int


class CustomTag(NamedTuple):
    """Named tuple for custom tag processing."""

    name: str
    processor: Callable
    cleaner: Callable | None = None


class BackfillMissingReportABC(TaskABC):
    """Scheduled Task"""

    def __init__(self, settings: SettingModel, tcex: TcEx, db: JsonDB, *, sdk=None):
        """Initialize the class."""
        super().__init__(settings, tcex, db)
        self.sdk = sdk
        self.owner = self.settings.tc_owner
        self.dao = ReportPdfTrackerDAO(self.db)
        self.custom_tags = [
            CustomTag(
                name=self.task_settings.pending_tag,
                processor=self.retrieve_document,
                cleaner=self.document_attached_cleanup,
            )
        ]
        self.supported_types = ['Report']

    def register_custom_tag(self, custom_tag: CustomTag):
        """Register custom tag."""
        self.custom_tags.append(custom_tag)

    @abstractmethod
    def retrieve_document(self, report_id: str):
        """Retrieve document from external source."""

    def document_attached_cleanup(self, report_id: str):  # noqa: ARG002
        """Retrieve document from external source."""
        return

    def _max_attempts_reached(self, group_id: int, tracker: ReportPdfTrackerModel):
        """Validate tracker."""
        if tracker.attempt_count >= self.task_settings.max_attempts:
            self.log.info(f'action=skip-group, group={group_id}, reason=attempt-count-exceeded')
            return True
        return False

    def _remove_tag(self, group: Group, tag):
        """Remove PDF Pending tag.

        Deliberately swallows failures: this used to be called with nothing catching it,
        so a single failed PUT (e.g. an upstream API error) would raise out of the entire
        `run()` loop, abort every other group queued in that cycle, and skip the tracker
        save for this group — leaving the tag in place forever and the group re-matching
        `groups()` on every 15s poll indefinitely. Logging and moving on is what actually
        keeps one bad group from taking the whole batch down with it.
        """
        tag_delete_body = {'tags': {'data': [{'name': tag}], 'mode': 'delete'}}
        try:
            self.tcex.session.tc.put(f'/v3/groups/{group.model.id}', json=tag_delete_body)
            self.log.debug(f'action=remove-tag, Removed tag={tag}')
        except Exception:
            self.log.exception(f'action=remove-tag-failed, group={group.model.id}, tag={tag}')

    def _update_tracker(self, tracker: ReportPdfTrackerModel):
        """Find existing tracker."""
        tracker.attempt_count += 1
        self.dao.save(tracker)

    def _upload_report_pdf(self, group: Group, document: bytes) -> tuple[bool, str]:
        """Upload report PDF."""
        if not group.model.xid:
            return False, f'Group {group.model.id} does not have an XID.'
        try:
            group = self.tcex.api.tc.v3.group(xid=group.model.xid)
            group.get(params={'owner': self.settings.tc_owner})
            response = group.upload(document, params={'updateIfExists': 'true'})
            if response.ok:
                return True, 'Success'
            return False, str(response.text)[:255]
        except Exception as ex:
            self.log.exception('task-event=backfill-pdf-failed')
            message = f'Unexpected error while uploading PDF ({ex}).'
            return False, message[:255]

    def launch(self):
        """Launch the task."""
        self.process = self.process_metadata()
        self.process.start()
        self.log.info(f'event=launch, action={self.task_settings.name}, pid={self.process.pid}')

    def launch_preflight_checks(self):
        """Run pre-flight check before launching task."""
        self.log.info(f'event=launch-preflight-check, action={self.task_settings.name}')
        self.launch()

    def groups(self, tag) -> Groups:
        """Return groups."""
        groups = self.tcex.api.tc.v3.groups(params={'fields': ['attributes']})

        groups.filter.owner_name(TqlOperator.EQ, self.owner)
        groups.filter.type_name(TqlOperator.IN, self.supported_types)
        groups.filter.has_tag.name(TqlOperator.EQ, tag)

        if len(groups) > 0:
            self.log.info(f'action=process-backfill-missing-report, group-count={len(groups)}')
            self.log.debug(f'tql={groups.tql.as_str}')

        return groups

    def run(self):
        """Create new request and download Mandiant Data."""
        try:
            for custom_tag in self.custom_tags:
                # iterate over groups
                for group in self.groups(custom_tag.name):
                    self._process_group(custom_tag, group)
        except Exception:
            self.log.exception('action=backfill-document, event=error')

    def _process_group(self, custom_tag: CustomTag, group: Group):
        """Attempt (or skip) one group for one custom tag. Split out of `run()` for C901/PLR0912."""
        # update the task heartbeat
        self.update_heartbeat()

        self.log.info(f'action=process-group, name={group.model.name} id={group.model.id}')

        report_id = self._external_id(group)
        if report_id is None:
            self.log.error(
                'action=process-backfill-missing-report, '
                'error=no-external-id, '
                f'group-id={group.model.id}'
            )
            return

        tracker = self.dao.find_next_for_group(report_id)
        tracker = tracker or ReportPdfTrackerModel(group_id=report_id, attempt_count=0)

        if self._skip_if_maxed(group, tracker, custom_tag):
            return

        document = None
        try:
            document = custom_tag.processor(report_id)
        except DocumentRetrievalError as ex:
            self.handle_failure(tracker, str(ex), group, report_id, custom_tag)
            return

        if document is None:
            self.handle_failure(
                tracker, 'Failed to download document', group, report_id, custom_tag
            )
            return

        success, message = self._upload_report_pdf(group, document)
        if not success:
            self.handle_failure(tracker, message, group, report_id, custom_tag)
            return

        # Persist first: a `_remove_tag` failure must not be able to drop this save (it
        # can't raise here either way now, but keep the ordering safe regardless of that).
        tracker.attempt_result = message
        self._update_tracker(tracker)
        self._remove_tag(group, custom_tag.name)
        if custom_tag.cleaner:
            custom_tag.cleaner(report_id)

    def _external_id(self, group: Group) -> str | None:
        """Return the group's External ID attribute value, or None if it has none."""
        for attribute in group.attributes:
            if attribute.model.type == 'External ID':
                return str(attribute.model.value)
        return None

    def _skip_if_maxed(
        self, group: Group, tracker: ReportPdfTrackerModel, custom_tag: CustomTag
    ) -> bool:
        """Return True if this group is already past `max_attempts`.

        Already past the ceiling — don't burn a real download/upload attempt on it, and
        don't touch `attempt_count` either; it stays frozen at the cap. The tag *should*
        have been removed already; this only re-tries that specific call, on an interval,
        in case the removal itself is what's failing. Paced off `date_added` (stable,
        already on the group) rather than persisting our own timestamp — lands in exactly
        one ~15s poll window per interval, no state needed.
        """
        if not self._max_attempts_reached(group.model.id, tracker):
            return False
        elapsed = datetime.datetime.now(datetime.UTC) - group.model.date_added
        interval = self.task_settings.retry_remove_tag_interval_seconds
        if elapsed.total_seconds() % interval < self.task_settings.schedule_period:
            self._remove_tag(group, custom_tag.name)
        return True

    def handle_failure(self, tracker, message, group, report_id, custom_tag):
        """Handle failure of PDF download or upload."""
        tracker.attempt_result = message
        self._update_tracker(tracker)
        if self._max_attempts_reached(group.model.id, tracker):
            # remove tag if we hit max retries
            self._remove_tag(group, custom_tag.name)
            if custom_tag.cleaner:
                custom_tag.cleaner(report_id)

    @cached_property
    def task_settings(self):
        """Return the task settings."""
        return TaskSettingCustomModel(
            description=(
                'Downloads missing documents then upload the files to the ThreatConnect Platform.'
            ),
            max_attempts=6,
            max_execution_minutes=20,
            name='Monitor TI Reports',
            pending_tag='PDF Pending',
            retry_remove_tag_interval_seconds=3600,
            schedule_period=15,
            schedule_unit='seconds',
        )
