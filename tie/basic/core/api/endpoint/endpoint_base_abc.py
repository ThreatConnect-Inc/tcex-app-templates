"""Endpoint Base Class"""

from tcex.logger.trace_logger import TraceLogger
from tcex.tcex import TcEx

from core.json_db import JsonDB
from model.settings_model import SettingModel

# TODO: What to do about tasks here?
# from core.task.tasks import Tasks
from sdk.sdk import SDK


class EndpointBaseABC:
    """Endpoint Base Class"""

    ##################################################
    # injected by TcEx middleware
    log: TraceLogger
    tcex: TcEx
    ##################################################

    ##################################################
    # injected by Injectable middleware
    db: JsonDB
    settings: SettingModel
    # tasks: Tasks
    sdk: SDK
