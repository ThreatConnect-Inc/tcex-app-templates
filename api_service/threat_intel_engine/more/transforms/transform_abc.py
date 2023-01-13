"""Transform ABC"""
# standard library
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Union

# third-party
from tcex.backports import cached_property

# first-party
from more import DbUtil, Metrics, session

if TYPE_CHECKING:
    # third-party
    from pydantic import BaseModel
    from tcex import TcEx

logger = logging.getLogger('tcex')


class TransformABC(ABC):
    """Transform ABC"""

    def __init__(
        self,
        settings: 'BaseModel',
        tcex: 'TcEx',
    ):
        """Initialize class properties."""
        self.settings = settings
        self.tcex = tcex

        # properties
        self.db = DbUtil()
        self.log = logger
        self.metrics = Metrics()
        self.session = session
        self.ti_tracker = {
            'actor': {},
            'malware': {},
            'report': {},
            'vulnerability': {},
        }

    @staticmethod
    def _generate_xid(id_: Union[int, str], ti_type: str) -> str:
        """Generate group xids."""
        return f'{ti_type}-{id_}'.upper()

    @cached_property
    def _map_target_country(self):  # pylint: disable=no-self-use
        """Return target country map."""
        return {
            'Iran': 'Iran, Islamic Republic Of',
            'Lao': 'Lao People\'s Democratic Republic',
            'Palestine': 'Palestinian Territory',
            'South Korea': 'Korea, Republic Of',
            'North Korea': 'Korea, Democratic People\'s Republic Of',
            'Taiwan': 'Taiwan, Province Of China',
            'Vietnam': 'Viet Nam',
        }

    def _transform_datetime(self, timestamp: str) -> str:
        """Convert timestamp value to epoch."""
        try:
            return self.tcex.utils.any_to_datetime(timestamp).strftime('%Y-%m-%dT%H:%M:%SZ')
        except Exception:
            return None

    @cached_property
    @abstractmethod
    def transform(self) -> 'TransformABC':
        """Transform data to TC format."""
