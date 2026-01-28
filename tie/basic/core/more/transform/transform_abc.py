"""Abstract Base Class for Data Transformation"""

# standard library
import json
import logging
from abc import ABC
from functools import cached_property
from pathlib import Path

# third-party
from tcex import TcEx
from tcex.api.tc.ti_transform.model import GroupTransformModel, IndicatorTransformModel
from tcex.api.tc.ti_transform.ti_predefined_functions import (
    ProcessingFunctions,
    transform_builder_to_model,
)

# first-party
from model import JobRequestModel
from model.settings_model import SettingModel

logger = logging.getLogger('tcex')


class TransformABC(ABC):  # noqa: B024
    """Abstract Base Class for data transformation tasks in ThreatConnect."""

    def __init__(
        self,
        settings: SettingModel,
        tcex: TcEx,
        specific_path: Path,
        request: JobRequestModel | None = None,
        base_path: Path = Path('mapping'),
    ) -> None:
        """Initialize the TransformABC class with necessary properties."""
        self.request = request
        self.settings = settings
        self.tcex = tcex
        self.api = tcex.api
        self.base_path = base_path
        self.base_path = base_path
        self.custom_fns = {}
        self.log = logger
        self.fns = ProcessingFunctions(tcex)

        # Initialize transformation-specific properties
        self.register_custom_functions()
        self.fns.custom_fns.update(self.custom_fns)
        self.specific_path = self._ensure_json_extension(specific_path)

    def _ensure_json_extension(self, path: Path) -> Path:
        """Ensure the given path has a .json extension."""
        return path if path.suffix == '.json' else Path(f'{path}.json')

    def register_custom_functions(self) -> None:
        """Register additional custom functions."""
        return

    @property
    def transform(self) -> GroupTransformModel | IndicatorTransformModel:
        """Method for transforming data to ThreatConnect format."""
        return self.post_transform_hook(self.transform_json)

    def post_transform_hook(
        self, data: GroupTransformModel | IndicatorTransformModel
    ) -> GroupTransformModel | IndicatorTransformModel:
        """Customize the transformation data."""
        return data

    def pre_transform_hook(self, data: dict) -> dict:
        """Customize the transform builder json data."""
        return data

    @cached_property
    def transform_json(self) -> dict:
        """Load and return transformation configuration from a JSON file."""
        config_path = self.base_path / self.specific_path
        if not config_path.exists():
            msg = f'File not found: {config_path}'
            raise RuntimeError(msg)
        self.log.debug(f'Loading transformation configuration from {config_path}')
        with config_path.open(encoding='utf-8') as file:
            data = json.load(file)
        data = self.pre_transform_hook(data)
        data = transform_builder_to_model(data, self.fns)
        data = self.post_transform_hook(data)
        return data
