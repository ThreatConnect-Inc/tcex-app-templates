"""ThreatConnect Preflight Check Service"""

import sqlite3
from collections.abc import Callable
from logging import Logger
from pathlib import Path
from typing import Any

import uuid6
from pydantic import BaseModel, model_validator

from core.json_db import JsonDB
from core.model.tie import (
    BatchErrorModel,
    ReportPdfTrackerModel,
    TiProcessingMetricModel,
)
from model.job_request_model import JobRequestModel
from model.settings_model import SettingModel


class SQLiteMigrationModel(BaseModel):
    """Model for migration."""

    table_name: str
    model: type[BaseModel]
    query: str | None = None
    row_callback: Callable | list[Callable] | None = None
    post_migration_callback: Callable[[list], list] | None = None

    @model_validator(mode='before')
    @classmethod
    def validate_data(cls, values: dict) -> dict:
        """Define the query if not provided."""
        if not values.get('query'):
            values['query'] = f'SELECT * FROM {values["table_name"]}'  # nosec

        row_callback = values.get('row_callback')
        if row_callback and not isinstance(row_callback, list):
            values['row_callback'] = [row_callback]

        return values

    def trigger_post_migration_callback(self, model_objects: list) -> list:
        """Trigger the callbacks."""
        if not self.post_migration_callback:
            return model_objects
        return self.post_migration_callback(model_objects)

    def trigger_row_callbacks(self, row: dict) -> dict | None:
        """Trigger the callbacks."""
        if not self.row_callback:
            return row
        for callback in self.row_callback:
            row = callback(row)
            if row is None:
                return None
        return row


class SQLiteMigration:
    """SQLite migration service."""

    def __init__(self, db_path: Path, json_db: JsonDB, log: Logger, settings: SettingModel):
        """Init SQLiteMigration."""
        self.log = log
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None
        self.json_db = json_db
        self.settings = settings
        self.table_models = [
            SQLiteMigrationModel(
                table_name='job_request',
                model=JobRequestModel,
                query='SELECT * FROM job_request order by date_queued',
                row_callback=self.job_request_row_transform,
            ),
            SQLiteMigrationModel(
                table_name='batch_error',
                model=BatchErrorModel,
                row_callback=self.batch_error_row_transform,
            ),
            SQLiteMigrationModel(
                table_name='report_pdf_tracker',
                model=ReportPdfTrackerModel,
                row_callback=self.report_pdf_tracker_row_transform,
            ),
            SQLiteMigrationModel(
                table_name='ti_processing_metric_schema',
                model=TiProcessingMetricModel,
                row_callback=self.ti_processing_metric_schema_row_transform,
            ),
        ]
        self.request_id_map: dict[str, str] = {}

    def ti_processing_metric_schema_row_transform(self, row: dict) -> dict | None:
        """Transform the ti_processing_metric_schema row data before processing."""
        if row['id'] is not None:
            del row['id']
        return row

    def report_pdf_tracker_row_transform(self, row: dict) -> dict | None:
        """Transform the report_pdf_tracker row data before processing."""
        if row['id']:
            row['group_id'] = row.pop('id')
        return row

    def track_request_id(self, request_id: str, uuid7: str) -> None:
        """Track a request ID to a UUID7."""
        self.request_id_map[request_id] = uuid7

    def get_uuid7(self, request_id: str) -> str | None:
        """Get the tracked UUID7 for a request ID."""
        return self.request_id_map.get(request_id)

    def add_row_callback(self, table_name: str, callback: Callable[[dict], dict | None]) -> None:
        """Add a row callback to a migration."""
        for migration in self.table_models:
            if migration.table_name == table_name:
                if not migration.row_callback:
                    migration.row_callback = []
                migration.row_callback.append(callback)

    def clear_row_callbacks(self, table_name: str) -> None:
        """Clear all row callbacks for a migration."""
        for migration in self.table_models:
            if migration.table_name == table_name:
                migration.row_callback = []

    def set_post_migration_callback(
        self, table_name: str, callback: Callable[[list], list] | None
    ) -> None:
        """Set a post migration callback for a migration."""
        for migration in self.table_models:
            if migration.table_name == table_name:
                migration.post_migration_callback = callback

    def remove_migration_model(self, table_name: str) -> None:
        """Remove a migration model for a specific table."""
        self.table_models = [
            migration for migration in self.table_models if migration.table_name != table_name
        ]

    def register_model_migration(
        self, table_model: SQLiteMigrationModel, replace: bool = False
    ) -> None:
        """Register a model for a specific table."""
        if replace:
            self.remove_migration_model(table_model.table_name)
        self.table_models.append(table_model)

    def fetch_table_data(self, query: str) -> list[dict[str, Any]]:
        """Fetch all rows from a table and return them as a list of dictionaries."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(query)
            column_names = [desc[0] for desc in cursor.description]
            return [dict(zip(column_names, row, strict=False)) for row in cursor.fetchall()]
        except sqlite3.Error:
            self.log.exception(f'Failed to execute query: {query}')
            return []

    def job_request_row_transform(self, row: dict) -> dict | None:
        """Transform the job_request row data before processing."""
        uuid7 = str(uuid6.uuid7())
        if row.get('request_id'):
            self.track_request_id(row['request_id'], uuid7)
            row['old_request_id'] = row.get('request_id')

        directory_name_stub = f'#{row.get("request_id")}'
        for d in self.settings.base_path.rglob(f'*{directory_name_stub}*'):
            if d.is_dir():
                if (r_file := d / 'request_id.txt').exists():
                    with Path.open(r_file, 'w', encoding='utf8') as f:
                        f.write(uuid7)
                d.rename(d.parent / d.name.replace(directory_name_stub, f'#{uuid7}'))
                break

        download_in_complete = row.get('date_download_complete') or row.get('date_failed')
        if download_in_complete is None and row.get('job_type', '') == 'scheduled':
            row['status'] = self.settings.job.status_pending
        row['request_id'] = uuid7
        return row

    def batch_error_row_transform(self, row: dict) -> dict | None:
        """Transform the batch_error row data before processing."""
        uuid7 = self.get_uuid7(row['request_id'])
        if not uuid7:
            msg = (
                'action=missing-mapped-request-id, '
                'table=batch_error, '
                f'row={row!s}, '
                f'request_id={row["request_id"]}'
            )
            self.log.warning(msg)
            return None
        row['request_id'] = uuid7
        return row

    def process_table(self, table_model: SQLiteMigrationModel) -> None:
        """Process all rows in a given table using the corresponding Pydantic model."""
        table_name = table_model.table_name
        model = table_model.model
        query = table_model.query
        self.log.info(f"Processing table '{table_name}' with model '{model.__name__}'")
        self.clear_json_db(model)

        model_objects = []
        for row_data in self.fetch_table_data(query):
            row_data = table_model.trigger_row_callbacks(row_data)
            if row_data is None:
                continue
            model_objects.append(model(**row_data))

        model_objects = table_model.trigger_post_migration_callback(model_objects)
        for model_object in model_objects:
            self.json_db.save(model_object)

    def should_migrate(self) -> bool:
        """Check if the database needs to be migrated."""
        return self.db_path.exists() and not self.db_path.name.endswith('_migrated.db')

    def rename_db(self) -> None:
        """Rename the database file to indicate that the migration has been completed."""
        try:
            new_db_path = self.db_path.with_name(
                f'{self.db_path.stem}_migrated{self.db_path.suffix}'
            )
            self.db_path.rename(new_db_path)
            self.log.info(f'event=rename-db, old_path={self.db_path}, new_path={new_db_path}')
        except Exception:
            self.log.exception('Failed to rename database')

    def clear_json_db(self, model) -> None:
        """Clear the JSON database before migrating."""
        self.log.info(f'action=clear-json-db, model={model.__name__}')
        for item in self.json_db.load_all(model):
            self.json_db.delete(item)

    def migrate(self) -> None:
        """Process all tables specified in the table-to-model mapping."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.log.info(f'Connected to database at {self.db_path}')
            for table_model in self.table_models:
                self.process_table(table_model)
            self.log.info('SQLite migration completed.')
        finally:
            if self.conn:
                self.conn.close()
                self.log.info('Database connection closed.')
