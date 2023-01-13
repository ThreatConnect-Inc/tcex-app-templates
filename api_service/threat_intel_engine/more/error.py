"""Error Module"""
# standard library
import logging
import sys
from inspect import getouterframes
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

if TYPE_CHECKING:
    # third-party
    import falcon

# logger
logger = logging.getLogger('tcex')


def get_frames():
    """Return a list of records for the stack above the caller's frame."""

    frames = []
    for f in getouterframes(sys._getframe(1), 1):  # pylint: disable=protected-access
        try:
            class_name = f'''{f.frame.f_locals['self'].__class__.__name__}.'''
        except KeyError:
            class_name = ''

        if 'site-packages' in f.filename:
            # entire frame is not helpful. break once a file outside of project is found
            break
        frames.append(
            f'''{f.frame.f_globals.get('__name__')}|{class_name}{f.function}:{f.lineno}'''
        )

    return frames[1:]


def error(
    title: str,
    description: str,
    headers: Optional[dict] = None,
    href: Optional[str] = None,
    href_text: Optional[str] = None,
    exception: Optional[str] = None,
    req: Optional['falcon.Request'] = None,
) -> dict:
    """Build and return an error dict containing all fields for an HTTPError in falcon.

    Supported fields: title, description, headers, href, href_text, code

    Data:
        status - Currently this is unused.
        title - Passed to the method. This typically matches error code.
        description - Passed to this method. A human readable explanation of error.
        headers - Currently this is unused.
        href - Currently this is unused.
        href_text - Currently this is unused.
        code - Records for the stack above the caller's frame.
    """
    frames = get_frames()
    code = str(uuid4())

    # build error log
    if isinstance(description, str):
        description = description.replace('"', '\\"')  # prevent quotes inside of quotes
    log_error = [f'code={code}', f'title="{title}"', f'description="{description}"']
    if req is not None:
        # append req properties if available
        log_error.append(f'path={req.path}')
        log_error.append(f'user_agent="{req.user_agent}"')

    # add frames to log error
    log_error.append(f'frames="{frames}"')

    if exception is not None:
        log_error.append(f'exception="{exception}"')

    # log error
    logger.error(', '.join(log_error))

    return {
        'code': code,
        'description': description,
        'headers': headers,
        'href': href,
        'href_text': href_text,
        'title': title,
    }
