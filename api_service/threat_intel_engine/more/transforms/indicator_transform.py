"""Transform for Actor"""
# standard library
from typing import TYPE_CHECKING

# third-party
from tcex.backports import cached_property

from .transform_abc import TransformABC

if TYPE_CHECKING:
    # third-party
    from tcex.api.tc.ti_transform.model import IndicatorTransformModel


class IndicatorTransform(TransformABC):
    """Transform for Actor"""

    @cached_property
    def transform(self) -> 'IndicatorTransformModel':
        """Return indicator mapping."""
        return self.tcex.api.tc.indicator_transform(
            {
                'value1': {'path': 'summary'},
                'type': {
                    'path': 'type',
                },
                'confidence': {
                    'default': 0,
                    'path': 'confidence',
                    'transform': [
                        {
                            'method': lambda c: c,
                        }
                    ],
                },
                'rating': {
                    'default': 0,
                    'path': 'rating',
                },
                'date_added': {'path': 'dateAdded'},
                'last_modified': {'path': 'lastModified'},
                'tags': [
                    {
                        'value': {
                            'path': 'tags[].name',
                            'transform': [
                                {
                                    'for_each': lambda n: n.toUpper(),
                                }
                            ],
                        },
                    }
                ],
                'xid': {'path': 'id', 'transform': {'method': lambda i: f'{i} - external'}},
            }
        )
