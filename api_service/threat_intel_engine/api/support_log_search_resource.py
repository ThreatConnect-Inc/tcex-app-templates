"""Class for /api/support/log-search endpoint"""
# standard library
import gzip
import os
import re
import sys
from typing import IO, TYPE_CHECKING

# third-party
from api.resource_abc import ResourceABC
from model.filter_param_model import FilterParamPaginatedModel
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    # third-party
    import falcon


class LogEventModel(BaseModel):
    """Log Event Model"""

    date: str = Field(..., description='The date of the log event.')
    filename: str = Field(..., description='The filename of the log event.')
    level: str = Field(..., description='The log level of the log event.')
    message: str = Field(..., description='The message of the log event.')
    method_name: str = Field(..., description='The method name of the log event.')
    line_number: int = Field(..., description='The line number of the log event.')
    request_id: str | None = Field(..., description='The request ID of the log event.')
    task_name: str | None = Field(..., description='The name of the task for the log event.')
    thread_name: str = Field(..., description='The thread name of the log event.')


class GetQueryParamModel(FilterParamPaginatedModel):
    """Params Model"""

    level: str = Field(None, description='')
    filename: str = Field(None, description='')
    # message: Pattern = Field(None, description='')
    method_name: str = Field(None, description='')
    request_id: str = Field(None, description='')
    task_name: str = Field(None, description='')
    thread_name: str = Field(None, description='')


class SupportLogSearchResource(ResourceABC):
    """Class for /api/support/log-search endpoint"""

    line_number = 0
    line_number_matched = 0
    validation_models = {
        'GET': {
            'request': {
                'query_params': GetQueryParamModel,
            }
        },
    }

    # pylint: disable=too-many-return-statements
    @staticmethod
    def _filter_log_event(event: LogEventModel, params: GetQueryParamModel) -> bool:
        """Filter log events based on the provided params."""
        if params.filename is not None and params.filename.lower() != event.filename.lower():
            return True

        if params.level is not None and params.level.lower() != event.level.lower():
            return True

        if (
            params.method_name is not None
            and params.method_name.lower() != event.method_name.lower()
        ):
            return True

        if params.request_id is not None and event.request_id is not None:
            if params.request_id.lower() != event.request_id.lower():
                return True

        if params.task_name is not None:
            # if there is not task name to match filter, exclude this event
            if event.task_name is None:
                return True
            if params.task_name.lower() != event.task_name.lower():
                return True

        if (
            params.thread_name is not None
            and params.thread_name.lower() != event.thread_name.lower()
        ):
            return True

        return False

    @staticmethod
    def _parse_log_event(log_event: str) -> dict:
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
            **{
                'date': event.group('log_date'),
                'filename': filename,
                'level': event.group('log_level'),
                'message': event.group('log_message'),
                'method_name': method_name,
                'line_number': line_number,
                'task_name': task_name,
                'thread_name': thread_name,
                'request_id': task_request_id,
            }
        )

    def _process_log_file(self, fh: IO, params: GetQueryParamModel) -> list:
        """Process a log file and return a list of log events."""
        events = []
        for line in fh.readlines():
            # skip logs from this file
            if os.path.basename(__file__) in line:
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
                parsed_data = self._parse_log_event(line)
                if parsed_data is None or self._filter_log_event(parsed_data, params) is True:
                    continue

                # add parsed data to event
                _event.update(parsed_data.dict())

                # increment line number matched
                self.line_number_matched += 1
            except Exception:
                # print to stderr instead of log to prevent erroring on this line
                print(f'Failed to parse log event: "{line}"', file=sys.stderr)
                continue

            events.append(_event)
        return events

    def on_get(self, req: 'falcon.Request', resp: 'falcon.Response'):
        """Handle GET requests.

        sort and sort_order are not supported.
        """
        # reset line number counts
        self.line_number = 0
        self.line_number_matched = 0

        response_media = []
        for log_file in sorted(self.tcex.inputs.model.tc_log_path.glob('app.log*'), reverse=True):
            if log_file.suffix == '.gz':
                with gzip.open(log_file, mode='rt', encoding='utf-8') as fh:
                    events = self._process_log_file(fh, req.context.params)
            else:
                with log_file.open(mode='r', encoding='utf-8') as fh:
                    events = self._process_log_file(fh, req.context.params)

            response_media.extend(events)
            # handle pagination
            if self.line_number_matched >= req.context.params.limit:
                break
        resp.media = response_media
