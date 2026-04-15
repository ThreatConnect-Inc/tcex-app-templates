"""Scheduled Task"""

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
        """Remove PDF Pending tag."""
        tag_delete_body = {'tags': {'data': [{'name': tag}], 'mode': 'delete'}}
        self.tcex.session.tc.put(f'/v3/groups/{group.model.id}', json=tag_delete_body)
        self.log.debug(f'action=remove-tag, Removed tag={tag}')

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
                    # update the task heartbeat
                    self.update_heartbeat()

                    self.log.info(
                        f'action=process-group, name={group.model.name} id={group.model.id}'
                    )

                    for attribute in group.attributes:
                        if attribute.model.type == 'External ID':
                            report_id = str(attribute.model.value)
                            break
                    else:
                        self.log.error(
                            'action=process-backfill-missing-report, '
                            'error=no-external-id, '
                            f'group-id={group.model.id}'
                        )
                        continue

                    tracker = self.dao.find_next_for_group(report_id)
                    tracker = tracker or ReportPdfTrackerModel(group_id=report_id, attempt_count=0)

                    document = None
                    try:
                        document = custom_tag.processor(report_id)
                    except DocumentRetrievalError as ex:
                        self.handle_failure(tracker, str(ex), group, report_id, custom_tag)
                        continue

                    if document is None:
                        self.handle_failure(
                            tracker,
                            'Failed to download document',
                            group,
                            report_id,
                            custom_tag,
                        )
                        continue

                    success, message = self._upload_report_pdf(group, document)
                    if success:
                        tracker.attempt_result = message
                        self._remove_tag(group, custom_tag.name)
                        self._update_tracker(tracker)
                        if custom_tag.cleaner:
                            custom_tag.cleaner(report_id)
                    else:
                        self.handle_failure(tracker, message, group, report_id, custom_tag)
        except Exception:
            self.log.exception('action=backfill-document, event=error')

    def handle_failure(self, tracker, message, group, report_id, custom_tag):
        """Handle failure of PDF download or upload."""
        tracker.attempt_result = message
        tracker.attempt_count += 1
        if self._max_attempts_reached(group.model.id, tracker) is True:
            # remove tag if we hit max retries
            self._remove_tag(group, custom_tag.name)
            if custom_tag.cleaner:
                custom_tag.cleaner(report_id)
        self._update_tracker(tracker)

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
            schedule_period=15,
            schedule_unit='seconds',
        )
