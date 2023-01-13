"""Logger middleware module."""
# standard library
import logging
import os
import traceback
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # standard library
    from typing import Optional

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


def app_exception(ex: Exception, message: 'Optional[str]' = None):
    """Handle exception consistently."""
    # build error log
    log_error = []

    if message:
        log_error.append(f'message="{message}"')

    # add cause if available
    cause_log_data = []
    if ex.__cause__:
        cause_log_data = build_log_traceback(ex.__cause__.__traceback__)
        log_error.append(f'cause="{ex.__cause__} -> {cause_log_data}"')

    # add traceback lines to log error
    ex_log_data = build_log_traceback(ex.__traceback__)
    log_error.append(f'exception="{ex_log_data}"')

    # log error
    logger.error(', '.join(log_error))

    if ex.__cause__:
        logger.error([line.strip() for line in traceback.format_tb(ex.__cause__.__traceback__)])
    logger.error([line.strip() for line in traceback.format_tb(ex.__traceback__)])

    # log full stack if in TRACE logging
    if logger.level == 5:
        logger.error(traceback.format_exc())


# define Python user-defined exceptions
class AppException(Exception):
    """App exception class for other exceptions"""

    def __init__(self, message: 'Optional[str]' = None):
        """."""
        super().__init__(message)

        # log exception
        app_exception(self)
