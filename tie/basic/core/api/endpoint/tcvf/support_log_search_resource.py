"""Class for /api/support/log-search endpoint"""

import gzip
import re
import sys
from pathlib import Path
from typing import IO

from pydantic import Field
from spectree import Response

from core.api.endpoint.tcvf.endpoint_base import EndpointBase
from core.api.falcon_request import FalconRequest
from core.api.falcon_response import FalconResponse
from core.api.spec import spec, tag_util
from core.api.validation.models.query_param_filter_pagination_model import (
    QueryParamFilterPaginationModel,
)
from core.model.log_event_model import LogEventModel, LogEventPaginatedResponseModel


class GetQueryParamModel(QueryParamFilterPaginationModel):
    """Params Model"""

    level: str = Field(None, description='')
    filename: str = Field(None, description='')
    # message: Pattern = Field(None, description='')
    method_name: str = Field(None, description='')
    request_id: str = Field(None, description='')
    task_name: str = Field(None, description='')
    thread_name: str = Field(None, description='')


class SupportLogSearchResource(EndpointBase):
    """Class for /api/support/log-search endpoint"""

    line_number = 0
    line_number_matched = 0

    @staticmethod
    def _log_event_matches(event: LogEventModel, params: GetQueryParamModel) -> bool:
        """Filter log events based on the provided params."""
        matches = True

        if params.filename is not None:
            matches = matches and params.filename.casefold() == event.filename.casefold()

        if params.level is not None:
            matches = matches and params.level.casefold() == event.level.casefold()

        if params.method_name is not None:
            matches = matches and params.method_name.casefold() == event.method_name.casefold()

        if params.request_id is not None:
            if event.request_id is None:
                matches = matches and params.request_id.casefold() in event.message.casefold()
            else:
                matches = matches and params.request_id.casefold() == event.request_id.casefold()

        if params.task_name is not None:
            # if there is not task name to match filter, exclude this event
            matches = (
                matches
                and event.task_name is not None
                and params.task_name.casefold() == event.task_name.casefold()
            )

        if params.thread_name is not None:
            matches = matches and params.thread_name.casefold() == event.thread_name.casefold()

        return matches

    @staticmethod
    def _parse_log_event(log_event: str, file_name: str) -> LogEventModel | None:
        """Parse a log event and return a dict with the parsed data."""
        # remove any new lines before parsing
        log_event = log_event.replace('\n', '')

        # parse log event
        parse_pattern = (
            # log date
            r'^(?P<log_date>[0-9]{4}-[0-9]{2}-[0-9]{2}\s[0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{0,6})'
            r'\s-\stcex\s-\s{0,5}'
            # log level
            r'(?P<log_level>ERROR|WARNING|INFO|DEBUG|TRACE)'
            r'\s-\s'
            # log message
            r'(?P<log_message>.*)'
            # log metadata
            r'\((?P<log_metadata>.*)\)$'
        )
        event = re.match(parse_pattern, log_event)
        if event is None:
            return None

        # parse metadata
        filename, method_name, line_number, thread_data = event.group('log_metadata').split(':')

        # handle thread data
        task_name = None
        task_request_id = None
        thread_name = thread_data
        if '|' in thread_data:
            task_name, task_request_id = thread_data.split('|')
        return LogEventModel(
            date=event.group('log_date'),
            filename=filename,
            level=event.group('log_level'),
            message=event.group('log_message'),
            method_name=method_name,
            line_number=line_number,
            task_name=task_name,
            thread_name=thread_name,
            request_id=task_request_id,
            log_file=file_name,
        )

    def _process_log_file(self, fh: IO, file_name: str, params: GetQueryParamModel) -> list:
        """Process a log file and return a list of log events."""
        events = []
        for line in fh.readlines():
            # skip logs from this file
            if Path(__file__).name in line:
                continue

            # increment line number
            self.line_number += 1

            # handle pagination
            if self.line_number_matched >= params.limit:
                break

            # handle offset
            if self.line_number < params.offset:
                continue

            # parse log event
            _event = {
                '_raw': line,
                'logfile': fh.name,
            }
            try:
                parsed_data = self._parse_log_event(line, file_name)
                if parsed_data is None or not self._log_event_matches(parsed_data, params):
                    continue

                # add parsed data to event
                _event.update(parsed_data.dict())

                # increment line number matched
                self.line_number_matched += 1
            except Exception:
                # print to stderr instead of log to prevent erroring on this line
                print(f'Failed to parse log event: "{line}"', file=sys.stderr)  # noqa: T201
                continue

            events.append(_event)
        return events

    @spec.validate(
        query=GetQueryParamModel,
        resp=Response(HTTP_200=LogEventPaginatedResponseModel),
        skip_validation=True,
        tags=[tag_util],
    )
    def on_get(
        self,
        _req: FalconRequest,
        resp: FalconResponse,
        query_params: GetQueryParamModel,
    ):
        """Search log files (sort and sort_order are not supported)."""
        # reset line number counts
        self.line_number = 0
        self.line_number_matched = 0

        response_media = []

        # current log files
        for log_file in sorted(self.tcex.inputs.model.tc_log_path.glob('*.log'), reverse=True):
            if log_file.suffix == '.gz':
                with gzip.open(log_file, mode='rt', encoding='utf-8') as fh:
                    events = self._process_log_file(fh, log_file.name, query_params)
            else:
                with log_file.open(mode='r', encoding='utf-8') as fh:
                    events = self._process_log_file(fh, log_file.name, query_params)

            response_media.extend(events)
            # handle pagination
            if self.line_number_matched >= query_params.limit:
                break

        if self.line_number_matched < query_params.limit:
            # archived log files
            for log_file in sorted(
                self.tcex.inputs.model.tc_log_path.glob('*.log.gz'), reverse=True
            ):
                if log_file.suffix == '.gz':
                    with gzip.open(log_file, mode='rt', encoding='utf-8') as fh:
                        events = self._process_log_file(fh, log_file.name, query_params)
                else:
                    with log_file.open(mode='r', encoding='utf-8') as fh:
                        events = self._process_log_file(fh, log_file.name, query_params)

                response_media.extend(events)
                # handle pagination
                if self.line_number_matched >= query_params.limit:
                    break

        resp_data = {
            'totalCount': -1,
            'count': len(response_media),
            'data': response_media,
        }
        resp.media = resp.response_model(resp_data, LogEventPaginatedResponseModel, query_params)
