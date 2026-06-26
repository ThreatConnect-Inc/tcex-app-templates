"""Metrics Module"""

import gzip
import json
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, root_validator

from core.json_db import JsonDB
from core.json_db.dao import JsonDBDAO
from core.model.tie import TiProcessingMetricModel
from core.util.custom_handler import CustomHandler
from model.job_request_model import JobRequestModel


class WritingModel(BaseModel):
    """Model for writing data to disk."""

    page_name: str
    output_dir: Path
    force: bool = False
    size: int = 5_000
    update_metrics: bool = False
    priority: str | None = None
    file_separator: str = '#'
    metric_name: str | None = None

    @root_validator
    def root_validation(cls, values):
        """Validate the model."""
        if not values.get('metric_name'):
            values['metric_name'] = values['page_name'].title()
        return values

    @property
    def full_path(self):
        """Return full path to the file."""
        return self.output_dir / self.file_name

    @property
    def file_name(self):
        """Return new filename for the given type."""
        file_name_identifiers = []
        if self.priority is not None:
            file_name_identifiers.append(self.priority)
        file_name_identifiers.append(str(round(time.time() * 10_000_000)))
        file_name_identifiers.append(self.page_name)
        name = f'{self.file_separator}'.join(file_name_identifiers).lower()
        return f'{name}.json.gz'

    def should_write(self, data):
        """Determine if data should be written to disk."""
        if not data:
            return False
        if self.force is True:
            return True
        if len(data) >= self.size:
            return True
        return False

    def should_write_batch(self, data: dict):
        """Determine if data should be written to disk."""
        return self.should_write(
            data.get('group', []) + data.get('indicator', []) + data.get('association', [])
        )


class WritingService:
    """Metrics Module"""

    def __init__(self, db: JsonDB, log, request: JobRequestModel | None = None):
        """Initialize class properties."""
        self.db = db
        self.request = request
        self.log = log
        self.file_separator = '#'
        self.metric_name_mapping = {}

    def register_metric_name_mapping(self, initial_type: str, mapped_type: str):
        """Register a batch transform."""
        self.metric_name_mapping[initial_type.lower()] = mapped_type

    def write_groups(self, data, writer: WritingModel):
        """Write groups to disk."""
        return self._write(data, writer, 'group')

    def write_indicators(self, data, writer: WritingModel):
        """Write indicators to disk."""
        return self._write(data, writer, 'indicator')

    def write_associations(self, data, writer: WritingModel):
        """Write associations to disk."""
        if not writer.should_write(data):
            return data

        while len(data) > writer.size or (writer.force and data):
            written_chunk, data = data[: writer.size], data[writer.size :]
            self.log.info(
                f'action=write-results, page_name={writer.page_name}, count={len(written_chunk)}'
            )
            self._write_data(written_chunk, writer)

        return data

    def write_batch(self, data, writer: WritingModel):
        """Write groups and indicators to disk."""
        if not writer.should_write_batch(data):
            return data

        groups = data.get('group', [])
        indicators = data.get('indicator', [])
        associations = data.get('association', [])

        total_data_length = len(groups) + len(indicators) + len(associations)

        while total_data_length > writer.size or (writer.force and total_data_length > 0):
            # Determine the number of items from each category to take
            groups_written_chunk, groups = groups[: writer.size], groups[writer.size :]
            indicator_chunk_size = writer.size - len(groups_written_chunk)
            indicators_written_chunk, indicators = (
                indicators[:indicator_chunk_size],
                indicators[indicator_chunk_size:],
            )
            association_chunk_size = indicator_chunk_size - len(indicators_written_chunk)
            associations_written_chunk, associations = (
                associations[:association_chunk_size],
                associations[association_chunk_size:],
            )

            total_data_length = len(groups) + len(indicators) + len(associations)

            # Create the chunk with the current set of groups and indicators
            chunk = {
                'group': groups_written_chunk,
                'indicator': indicators_written_chunk,
                'association': associations_written_chunk,
            }
            self.log.info(
                f'action=write-results, '
                f'page_name={writer.page_name}, '
                f'group-chunk={len(groups_written_chunk)}, '
                f'indicator-chunk={len(indicators_written_chunk)}, '
                f'association-chunk={len(associations_written_chunk)}'
            )
            self._write_data(chunk, writer)
            if writer.update_metrics:
                self.update_batch_metrics(chunk)

        return {'group': groups, 'indicator': indicators, 'association': associations}

    @staticmethod
    def _write_data(data, writer: WritingModel):
        """Write data to disk."""
        with gzip.open(writer.full_path, 'wt', encoding='utf-8', compresslevel=9) as f:
            json.dump(data, f, cls=CustomHandler)

    def update_metrics(self, data, writer, type_: Literal['group', 'indicator']):
        """Update metrics."""
        if not self.request:
            self.log.warning('action=write, message="Request not set, cannot update metrics"')
            return

        aggregated_counts = {
            writer.metric_name: len(data),
            'total_groups': 0,
            'total_indicators': 0,
        }
        if type_ == 'group':
            aggregated_counts['total_groups'] = len(data)
        else:
            aggregated_counts['total_indicators'] = len(data)

        self._update_metrics(aggregated_counts)

    def update_batch_metrics(self, data):
        """Update metrics"""
        if not self.request:
            self.log.warning('action=write-batch, message="Request not set, cannot update metrics"')
            return

        aggregated_counts = {
            'total_groups': len(data.get('group', [])),
            'total_indicators': len(data.get('indicator', [])),
        }
        for indicator in data.get('indicator', []):
            type_ = indicator.get('type')
            aggregated_counts.setdefault(type_, 0)
            aggregated_counts[type_] += 1
        for group in data.get('group', []):
            type_ = group.get('type')
            aggregated_counts.setdefault(type_, 0)
            aggregated_counts[type_] += 1

        self._update_metrics(aggregated_counts)

    def _update_metrics(self, aggregated_counts: dict):
        """Update metrics."""
        total_groups = aggregated_counts.pop('total_groups', 0)
        total_indicators = aggregated_counts.pop('total_indicators', 0)
        for type_, count in aggregated_counts.items():
            if type_.lower() in self.metric_name_mapping:
                type_ = self.metric_name_mapping[type_.lower()]
            dao = JsonDBDAO(self.db, TiProcessingMetricModel)
            try:
                metric = dao.get(type_)
            except FileNotFoundError:
                metric = TiProcessingMetricModel(ti_type=type_, ti_count=0)
            metric.ti_count += count
            msg = (
                'action=update-metrics, '
                f'type={type_}, '
                f'previous-count={metric.ti_count - count}, '
                f'new-count={metric.ti_count}'
            )
            self.log.debug(msg)
            dao.save(metric)

        self.request.count_download_group += total_groups
        self.request.count_download_indicator += total_indicators
        msg = (
            'action=update-metrics, '
            f'previous-groups={self.request.count_download_group - total_groups}, '
            f'previous-indicators={self.request.count_download_indicator - total_indicators}, '
            f'new-groups={self.request.count_download_group}, '
            f'new-indicators={self.request.count_download_indicator}'
        )
        self.log.info(msg)
        self.db.save(self.request)

    def _write(self, data: list, writer: WritingModel, type_: Literal['group', 'indicator']):
        """Write data"""
        if not writer.should_write(data):
            return data

        while len(data) > writer.size or (writer.force and data):
            written_chunk, data = data[: writer.size], data[writer.size :]
            self.log.info(
                f'action=write-results, page_name={writer.page_name}, count={len(written_chunk)}'
            )
            self._write_data(written_chunk, writer)

            if not writer.update_metrics:
                continue

            self.update_metrics(written_chunk, writer, type_)

        return data
