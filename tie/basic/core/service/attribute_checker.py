"""ThreatConnect Preflight Check Service"""

# standard library
import json
import logging
from functools import cached_property
from pathlib import Path
from typing import Any

# third-party
from tcex import TcEx

logger = logging.getLogger('tcex')


class AttributeChecker:
    """Service for performing preflight checks."""

    def __init__(self, tcex: TcEx):
        """Initialize class properties."""
        self.tcex: TcEx = tcex
        self.log = tcex.logger.log
        self.preflight_checks = set()

    @staticmethod
    def _norm_str(value: Any) -> str:
        return (str(value or '')).strip().lower()

    @cached_property
    def _local_attributes_file(self) -> dict:
        attributes_path = Path(__file__).resolve().parents[2] / 'attributes.json'
        self.log.info('attributes.json path: %s', attributes_path)
        if not attributes_path.exists():
            ex_msg = f'attributes.json file not found at {attributes_path}'
            self.log.error(ex_msg)
            raise RuntimeError(ex_msg)

        try:
            with attributes_path.open('r', encoding='utf-8') as fh:
                payload = json.load(fh)
            self.log.info('Loaded attributes from %s', attributes_path)
        except Exception:
            self.log.exception('Failed to load attributes.json file.')
            raise

        return payload

    @cached_property
    def local_attributes(self) -> dict[str, set[str]]:
        """{attribute_name_lower: set of supported type names (lowercased)}"""
        result: dict[str, set[str]] = {}
        for entry in self._local_attributes_file.get('types') or []:
            name = self._norm_str(entry.get('name'))
            if not name:
                continue

            groups = [self._norm_str(g) for g in entry.get('groups', [])]
            indicators = [self._norm_str(i) for i in entry.get('indicators', [])]

            # Merge and drop empties
            supported = {v for v in (groups + indicators) if v}
            result[name] = supported

        return result

    @cached_property
    def remote_attributes(self) -> dict[str, set[str]]:
        """Return {attribute_name_lower: set_of_supported_types_tokens} from the platform."""
        result: dict[str, set[str]] = {}
        params = {
            'resultLimit': 1_000,
            'fields': ['mapping'],
        }
        for at in self.tcex.api.tc.v3.attribute_types(params=params):
            try:
                model = at.model.dict()
                supported_types = {
                    self._norm_str(mapping.get('type'))
                    for mapping in model.get('attributeTypeMappings', [])
                }
                result[self._norm_str(model.get('name'))] = supported_types
            except Exception:
                self.log.exception('Error parsing remote attribute type.')
                continue
        return result

    @staticmethod
    def is_subset(subset: set[str], superset: set[str]) -> bool:
        """Return True if `subset` is a subset of `superset`."""
        return subset.issubset(superset)

    def is_valid(self) -> bool:
        """Validate that every local attribute exists remotely and supports a subset of types."""
        ok = True
        local = self.local_attributes
        remote = self.remote_attributes

        for attr_name, local_supported in local.items():
            if attr_name not in remote:
                ok = False
                self.log.error(
                    'Preflight: attribute missing on platform: "%s" (local supports %s)',
                    attr_name,
                    sorted(local_supported),
                )
                continue

            remote_supported = remote[attr_name]
            if not self.is_subset(local_supported, remote_supported):
                ok = False
                missing = sorted(local_supported - remote_supported)
                msg = (
                    f'Preflight: attribute supported types mismatch for "{attr_name}". '
                    f'Missing on platform: {missing}'
                    f' | local={sorted(local_supported)} | remote={sorted(remote_supported)}'
                )
                self.log.error(msg)

        if ok:
            self.log.info(
                'Preflight attributes check passed: local attributes are compatible with platform.'
            )
        else:
            self.log.error('Preflight attributes check failed: see errors above for details.')

        return ok
