"""Custom HTTP Error Module"""
# standard library
import logging
import os
import traceback
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    # third-party
    import falcon


# logger
logger = logging.getLogger('tcex')


def build_log_traceback(tb: traceback) -> list:
    """."""
    frames = []
    for frame, lineno in traceback.walk_tb(tb):
        try:
            class_ = f'''{frame.f_locals['self'].__class__.__name__}.'''
        except KeyError:
            class_ = ''

        frames.append(
            {
                'class': class_,
                'fqfn': frame.f_code.co_filename,
                'function': frame.f_code.co_name,
                'lineno': lineno,
            }
        )

    # reverse lines to put the last error line first
    frames.reverse()
    log_data = []
    for frame in frames:
        class_ = frame.get('class')
        fqfn = frame.get('fqfn')
        filename = os.path.basename(frame.get('fqfn'))
        function = frame.get('function')
        lineno = frame.get('lineno')

        if 'site-packages' in fqfn:
            # entire frame is not always helpful. break once a file outside of project is found
            break

        # append log data
        log_data.append(f'{filename}|{class_}{function}:{lineno}')

    return log_data


# pylint: disable=W0613
def custom_error_handler(req: 'falcon.Request', resp: 'falcon.Response', ex, params: dict):
    """."""

    # update exception
    if ex.description is not None:
        ex.description = ex.description.replace('"', '\\"')  # prevent quotes inside of quotes
    ex.code = str(uuid4())

    # build error log
    log_error = [
        f'code={ex.code}',
        f'title="{ex.title}"',
        f'description="{ex.description}"',
        f'path={req.path}',
        f'user_agent="{req.user_agent}"',
    ]

    # append req

    # add cause if available
    cause_log_data = []
    if ex.__cause__:
        cause_log_data = build_log_traceback(ex.__cause__.__traceback__)
        log_error.append(f'cause="{ex.__cause__} -> {cause_log_data}"')

    # add traceback lines to log error
    ex_log_data = build_log_traceback(ex.__traceback__)
    log_error.append(f'exception="{ex.__traceback__} -> {ex_log_data}"')

    ex.headers = {
        'api_service_cause': ', '.join(cause_log_data),
        'api_service_exception': ', '.join(ex_log_data),
    }

    # log error
    logger.error(', '.join(log_error))

    # log full stack if in TRACE logging
    if logger.level == 5:
        if ex.__cause__:
            logger.error([line.strip() for line in traceback.format_tb(ex.__cause__.__traceback__)])
        logger.error([line.strip() for line in traceback.format_tb(ex.__traceback__)])

    raise ex
