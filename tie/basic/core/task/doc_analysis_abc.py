"""Scheduled Task"""

# standard library
from collections import namedtuple
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from itertools import zip_longest

# third-party
import requests
from data_model.doc_analysis import DocAnalysisData
from tcex import TcEx
from tcex.api.tc.v3.groups.group import Group, Groups
from tcex.api.tc.v3.tql.tql_operator import TqlOperator
from tcex.input.field_type import Sensitive
from tcex.pleb.cached_property import cached_property

# first-party
from core.dao.doc_analysis_processed_items_dao import DocAnalysisProcessedItemsDAO
from core.dao.doc_analysis_throttled_dao import DocAnalysisThrottledDAO
from core.dao.doc_analysis_tracker_dao import DocAnalysisTrackerDAO
from core.json_db import JsonDB
from core.model.tie.doc_analysis_processed_items_model import DocAnalysisProcessedItemsModel
from core.model.tie.doc_analysis_tracker_model import DocAnalysisTrackerModel
from core.model.tie.task_setting_model import TaskSettingModel
from core.task.task_abc import TaskABC
from model import SettingModel


class CALAuth(requests.auth.AuthBase):  # pylint: disable=too-few-public-methods
    """Token-based auth for CAL."""

    def __init__(self, token: str, timestamp: int):
        """Initialize CALAuth."""
        self.token = token
        self.timestamp = timestamp

    def __call__(self, r: requests.PreparedRequest):
        """Add CAL authorization headers."""
        r.headers['Authorization'] = self.token
        r.headers['Timestamp'] = str(self.timestamp)
        return r


CustomTag = namedtuple(  # noqa: PYI024
    'CustomTag', ['name', 'processor', 'cleaner'], defaults=[None, None, None]
)


class DocAnalysisABC(TaskABC):
    """Scheduled Task."""

    def __init__(self, settings: SettingModel, tcex: TcEx, db: JsonDB, *, sdk=None):
        """Initialize DocAnalysisABC."""
        super().__init__(settings, tcex, db)
        self.sdk = sdk
        self.owner = self.settings.tc_owner
        self.dao = DocAnalysisTrackerDAO(self.db)
        self.processed_items_dao = DocAnalysisProcessedItemsDAO(self.db)
        self.throttled_dao = DocAnalysisThrottledDAO(self.db)
        self.supported_types = ['Report']
        self.doc_analysis_features = {'alias', 'ioc', 'attack', 'textindustry', 'textsummarize'}
        self.doc_analysis_ttl = timedelta(days=7)
        self.custom_tags = []
        self._session = None
        self.max_attempts = 3
        self.pending_doc_analysis_tag = 'Doc Analysis Pending'
        self.max_groups_per_run = 1_000

    def tc_cal(self):
        """Get the ThreatConnect CAL token."""
        response = self.tcex.session.tc.post(
            '/internal/token/cal',
            headers={'Accept': 'application/json'},
        )

        response = response.json()['data']

        return {
            'timestamp': response['timestamp'],
            'token': Sensitive(response['token']),
        }

    def construct_session(self):
        """Construct the session."""
        self.log.debug('action=construct-session, message=constructing-new-session')
        new_session = self.tcex.requests_external.get_session()
        new_session.log_curl = True
        new_session.base_url = self.settings.tc_cal_host
        tc_cal = self.tc_cal()
        tc_cal_token = tc_cal['token']
        tc_cal_timestamp = tc_cal['timestamp']
        new_session.auth = CALAuth(tc_cal_token.value, tc_cal_timestamp)
        self.log.debug(f'action=construct-session, till={tc_cal_timestamp}, ')
        return new_session

    @property
    def session(self):
        """Return the session, constructing it if necessary."""
        if not self._session:
            self._session = self.construct_session()
        now = int(datetime.now(UTC).timestamp())
        # If the session is expired (5 second buffer)
        if (now - 5) > self._session.auth.timestamp:
            self._session = self.construct_session()
        return self._session

    def register_custom_tag(self, custom_tag: CustomTag):
        """Register a custom tag."""
        self.custom_tags.append(custom_tag)

    def _max_attempts_reached(self, group_id: int, tracker: DocAnalysisTrackerModel):
        """Check if max attempts reached."""
        if tracker.attempt_count >= self.max_attempts:
            self.log.info(f'action=skip-group, group={group_id}, reason=attempt-count-exceeded')
            return True
        return False

    def _update_tag(self, group: Group, tag, mode='delete'):
        """Remove a tag from a group."""
        tag_delete_body = {'tags': {'data': [{'name': tag}], 'mode': mode}}
        self.tcex.session.tc.put(f'/v3/groups/{group.model.id}', json=tag_delete_body)
        self.log.debug(f'action={mode}-tag, {mode} tag={tag}')

    def _update_tracker(self, tracker: DocAnalysisTrackerModel):
        """Update the tracker attempt count."""
        tracker.attempt_count += 1
        self.dao.save(tracker)

    def _reset_tracker(self, tracker: DocAnalysisTrackerModel):
        """Reset the tracker attempt count."""
        tracker.attempt_count += 0
        self.dao.save(tracker)

    def launch(self):  # pylint: disable=arguments-differ
        """Launch the task."""
        self.process = self.process_metadata()  # pylint: disable=attribute-defined-outside-init
        self.process.start()
        self.log.info(f'event=launch, action={self.task_settings.name}, pid={self.process.pid}')

    def launch_preflight_checks(self):
        """Run preflight checks before launching."""
        self.log.info(f'event=launch-preflight-check, action={self.task_settings.name}')
        throttle_remaining = self.throttled_dao.throttled_time_remaining()
        if throttle_remaining > 0:
            self.log.info(
                'task-event=doc-analysis-throttled, '
                'reason=doc-analysis-throttled, '
                'message=Doc Analysis is currently throttled.'
                f'time-remaining={throttle_remaining} seconds'
            )
            return
        self.throttled_dao.reset_throttle()
        self.launch()

    def groups(self, tag: str) -> Groups:
        """Return groups with a tag."""
        groups = self.tcex.api.tc.v3.groups(
            params={'fields': ['attributes'], 'resultLimit': self.max_groups_per_run}
        )
        groups.filter.owner_name(TqlOperator.EQ, self.owner)
        groups.filter.type_name(TqlOperator.IN, self.supported_types)
        groups.filter.has_tag.name(TqlOperator.EQ, tag)
        if len(groups) > 0:
            self.log.info(f'action=process-backfill-missing-report, group-count={len(groups)}')
            self.log.debug(f'tql={groups.tql.as_str}')
        return groups

    def run(self):
        """Run the document analysis task."""
        throttle_time = self.throttled_dao.throttled_time_remaining()
        if throttle_time > 0:
            self.tcex.log.warning(
                f'task-event=doc-analysis-throttled, remaining-seconds={throttle_time}'
            )
            return
        self.tcex.log.trace(f'task-event=doc-analysis-started, throttle-time={throttle_time}')
        processed_items = self.processed_items_dao.instance
        parsed_groups = {}
        try:
            for custom_tag in self.custom_tags:
                for group in self.groups(custom_tag.name):
                    id_ = group.model.id
                    self.update_heartbeat(verbose=False)
                    msg = f'action=processing-group, name={group.model.name}, id={id_}'
                    self.log.info(msg)
                    tracker = self.dao.find_next_for_group(id_)
                    tracker = tracker or DocAnalysisTrackerModel(group_id=id_, attempt_count=0)
                    try:
                        type_ = 'text'
                        if group.model.file_name.endswith('.html'):
                            type_ = 'html'
                        doc_analysis = self.get_doc_analysis(group.download(), type_=type_)
                        if not doc_analysis:
                            throttle_time = self.throttled_dao.throttled_time_remaining()
                            self.tcex.log.warning(
                                f'task-event=doc-analysis-throttled, seconds={throttle_time}'
                            )
                            return
                    except Exception:
                        self.tcex.log.exception(f'task-event=doc-analysis-failed, group={id_}')
                        self.handle_failure(tracker, 'get-doc-analysis-failed', group, custom_tag)
                        continue
                    self.throttled_dao.reset_throttle()
                    try:
                        parsed_groups = self.process_doc_analysis(
                            parsed_groups, processed_items, group, doc_analysis
                        )
                        self.process_groups(parsed_groups, processed_items)
                        self._update_tag(group, custom_tag.name)
                        self._update_tag(group, 'Doc Analysis', 'append')
                        tracker.attempt_count = 0
                        tracker.attempt_result = f'Success: {datetime.now(UTC).isoformat()}'
                        self._update_tracker(tracker)
                    except Exception:
                        self.tcex.log.exception(
                            f'task-event=enrich-with-doc-analysis-failed, group={id_}'
                        )
                        self.handle_failure(
                            tracker, 'enrich-with-doc-analysis-failed', group, custom_tag
                        )
            try:
                self.process_groups(parsed_groups, processed_items, force=True)
            except Exception:
                self.log.exception('task-event=process-groups-forced-failed')
            self.processed_items_dao.save_newest_items(processed_items)
        except Exception:
            self.log.exception('task-event=doc-analysis-failed')

    def get_doc_analysis(
        self,
        report: str | bytes,
        type_: str = 'text',
    ) -> DocAnalysisData | None:
        """Get document analysis results."""

        def truncate_report(report: str, max_length=100_000) -> str:
            """Truncate report to 100k characters."""
            if len(report) > max_length:
                self.tcex.log.warning(
                    f'event=truncate-report, report-length={len(report)}, '
                    f'truncated-length={max_length}'
                )
                return report[:max_length]
            return report

        def normalize_report(report: str | bytes) -> str:
            """Normalize report to string."""
            if isinstance(report, str):
                return report
            return report.decode('utf-8')

        report = normalize_report(report)
        report = truncate_report(report)
        params = {
            'source': 'integrations',
            'apps': ','.join(self.doc_analysis_features),
            'output': 'clean',
        }
        if type_ == 'html':
            params['input'] = type_
        documents = [
            {
                'name': 'Flashpoint Ignite Threat Intelligence Engine',
                'text': report,
                'sourceId': 'http://threatconnect.com/api/services/flashpoint_intel',
                'shareable': 1,
            }
        ]
        req = self.session.post('/helix/document/v1/analyze', params=params, json=documents)
        if req.status_code == 429:
            self.throttled_dao.throttle()
            return None
        req.raise_for_status()
        req = req.json()
        return DocAnalysisData(data=req)

    def handle_failure(self, tracker, message, group, custom_tag):
        """Handle a failure in processing."""
        tracker.attempt_result = message
        tracker.attempt_count += 1
        if self._max_attempts_reached(group.model.id, tracker) is True:
            self._update_tag(group, custom_tag.name)
            if custom_tag.cleaner:
                custom_tag.cleaner(group.model.id)
        self._update_tracker(tracker)

    def process_group(self, xid, data, processed_items):
        """Process a single group."""
        associations = data.get('associations', set())
        timestamp = data.get('timestamp')
        data = data.get('data', {})
        group = self.tcex.api.tc.v3.group(**data)
        for id_ in associations:
            group.stage_associated_group({'id': id_})
        last_processed_time = processed_items.last_time_processed('groups', group.model.type, xid)
        if last_processed_time:
            self.log.debug(f'action=process-group, xid={xid}, last-processed={last_processed_time}')
            group.update()
            processed_items.track_processed('groups', group.model.type, xid, timestamp)
        else:
            self.log.debug(f'action=process-group, xid={xid}, creating new group')
            try:
                group.create()
                processed_items.track_processed('groups', group.model.type, xid, timestamp)
            except Exception as e:
                if 'XID is already in use' in str(e):
                    group.update()
                    processed_items.track_processed('groups', group.model.type, xid, timestamp)
                else:
                    self.tcex.log.exception('task-event=create-group-failed')

    def process_groups(
        self, parsed_groups: dict, processed_items: DocAnalysisProcessedItemsModel, force=False
    ):
        """Process and associate groups."""
        if len(parsed_groups) < 1_000 and force is False:
            return parsed_groups

        for xid, data in parsed_groups.items():
            try:
                self.process_group(xid, data, processed_items)
            except Exception:
                self.tcex.log.exception(f'task-event=process-group-failed, xid={xid}')
        return {}

    @property
    def value_1_map(self):
        """Return indicator field mapping."""
        return {
            'address': 'ip',
            'emailaddress': 'address',
            'email address': 'address',
            'file': 'md5',
            'host': 'hostName',
            'url': 'text',
            'asn': 'AS Number',
            'cidr': 'Block',
        }

    def process_indicators(
        self,
        processed_items: DocAnalysisProcessedItemsModel,
        report: Group,
        indicators: Generator[dict, None, None],
    ):
        """Process and associate indicators."""
        report_last_modified: int = report.model.last_modified.timestamp()  # type: ignore
        for indicator in indicators:
            value_1 = indicator.pop('value1')
            type_ = indicator.get('type', '').lower()
            self.log.debug(f'action=process-entity type={type_} name="{value_1}"')
            key = self.value_1_map.get(type_, None)
            value = 'value1'
            if type_ == 'file':
                keys = {
                    32: ('md5', 'value1'),
                    40: ('sha1', 'value2'),
                    64: ('sha256', 'value3'),
                }
                key, value = keys.get(len(value_1), ('md5', 'value1'))
            if not key:
                self.tcex.log.error(f'Unsupported indicator type: {type_}')
                continue
            indicator[key] = value_1
            last_modified = processed_items.last_time_processed(
                'indicators', indicator['type'], value_1
            )
            ti_indicator = self.tcex.api.tc.v3.ti.indicator(**indicator)
            if last_modified:
                report.stage_associated_indicator(ti_indicator)
                processed_items.track_processed(
                    'indicators',
                    indicator['type'],
                    value_1,
                    report_last_modified,
                )
                continue
            try:
                ti_indicator.create()
                report.stage_associated_indicator(ti_indicator)
                processed_items.track_processed(
                    'indicators',
                    indicator['type'],
                    value_1,
                    report_last_modified,
                )
            except Exception as e:
                if 'a File with this ' in str(e):
                    self.tcex.log.debug(f'Indicator exists: {indicator} - {value_1} ({key})')
                    ti_indicators = self.tcex.api.tc.v3.ti.indicators()
                    getattr(ti_indicators.filter, value)(TqlOperator.EQ, value_1)
                    ti_indicators.filter.type_name(TqlOperator.EQ, 'File')
                    found_indicator = None
                    for ti_indicator in ti_indicators:
                        if found_indicator:
                            self.tcex.log.error(  # noqa: TRY400
                                f'Found multiple indicators with value1={value_1}'
                            )
                            continue
                        found_indicator = ti_indicator.model
                    if found_indicator:
                        report.stage_associated_indicator(found_indicator)
                    else:
                        self.tcex.log.error(  # noqa: TRY400
                            f'No indicator found with value1={value_1}, type={indicator["type"]}'
                        )

                self.tcex.log.error(  # noqa: TRY400
                    f'Error processing indicator {indicator} - {value_1}'
                )
                continue

    def chunked(self, lst, size):
        """Split a list into chunks."""
        return [lst[i : i + size] for i in range(0, len(lst), size)]

    def update_report(self, report: Group):
        """Update the report in chunks."""
        chunk_size = 995
        tags = report.model.tags.data
        groups = report.model.associated_groups.data
        indicators = report.model.associated_indicators.data
        tag_chunks = self.chunked(tags, chunk_size)
        group_chunks = self.chunked(groups, chunk_size)
        indicator_chunks = self.chunked(indicators, chunk_size)
        for tag_chunk, group_chunk, indicator_chunk in zip_longest(
            tag_chunks, group_chunks, indicator_chunks, fillvalue=[]
        ):
            report.model.tags.data = tag_chunk
            report.model.associated_groups.data = group_chunk
            report.model.associated_indicators.data = indicator_chunk
            report.update()

    def merge_processed_groups(self, processed_groups: dict, group: Group, data: DocAnalysisData):
        """Merge processed groups with the parsed data."""
        last_modified = int(group.model.last_modified.timestamp())
        for doc_analysis_group in data.groups():
            xid = doc_analysis_group['xid']
            processed_groups.setdefault(
                xid,
                {
                    'associations': set(),
                    'timestamp': int(group.model.last_modified.timestamp()),
                    'data': doc_analysis_group,
                },
            )
            processed_groups[xid]['associations'].add(group.model.id)
            processed_groups[xid]['timestamp'] = max(
                processed_groups[xid]['timestamp'], last_modified
            )
        return processed_groups

    def process_doc_analysis(
        self,
        processed_groups: dict,
        processed_items: DocAnalysisProcessedItemsModel,
        report: Group,
        data: DocAnalysisData,
    ):
        """Process document analysis results."""
        # self.add_note(report, data.note)
        for mitigation in data.mitigation_attributes():
            report.stage_attribute(mitigation)
        report.stage_attribute(data.doc_analysis_attribute())
        self.process_indicators(processed_items, report, data.indicators())
        processed_groups = self.merge_processed_groups(processed_groups, report, data)
        # self.process_groups(processed_groups, processed_items, data.groups())
        for tag in data.tags['standard_tags'] | data.tags['naics_tags']:
            tag = self.tcex.api.tc.v3.tag(name=tag)
            report.stage_tag(tag)
        for tag in data.tags['mitre_tags']['extracted'] | data.tags['mitre_tags']['ai']:
            tag = self.tcex.api.tc.v3.ti.mitre_tags.get_by_id(tag, default=tag)
            tag = self.tcex.api.tc.v3.tag(name=tag)
            report.stage_tag(tag)
        self.update_report(report)
        return processed_groups

    def add_note(self, report: Group, note: str | None):
        """Add a note to a report."""
        if not note:
            return
        json_ = {
            'objectId': report.model.id,
            'objectType': 'Group',
            'text': note,
        }
        response = self.tcex.session.tc.post('/internal/posts', json=json_)
        response.raise_for_status()
        self.tcex.log.debug(f'action=add-note, len="{len(note)}" report={report.model.id}')

    @cached_property
    def task_settings(self):  # pylint: disable=invalid-overridden-method
        """Return the task settings."""
        return TaskSettingModel(
            description=('Enrich Threat Intelligence reports with Document Analysis.'),
            max_execution_minutes=20,
            name='Doc Analysis',
            schedule_period=10,
            schedule_unit='minutes',
            # schedule_period=15,
            # schedule_unit='seconds',
        )
