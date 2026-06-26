"""ThreatConnect Preflight Check Service"""

from pathlib import Path

from packaging.version import parse

from core.model.tie.version_manager_model import VersionManagerModel
from core.service.sqlite_migration_service import SQLiteMigration


class MigrationService:
    """Service for performing preflight checks."""

    def __init__(self, tcex, log, db, settings):
        """Initialize class properties."""
        self.tcex = tcex
        self.log = log
        self.db = db
        self.migrations = []

        # Doing this in the init so that it is always called and thus a instance of the migration
        # tracker is always guaranteed to exist.
        self.migration_tracker = self._migration_tracker

        # The sqldb might not exist for new installs so look for: app_store.db
        db_file = Path(self.tcex.inputs.model_path.tc_out_path / 'app_store.db')
        self.sql_lite_migration = SQLiteMigration(
            db_path=db_file, json_db=db, log=log, settings=settings
        )

    @property
    def _migration_tracker(self):
        """Return the migration tracker."""
        migration_tracker = list(self.db.load_all(VersionManagerModel))
        if migration_tracker:
            return migration_tracker[0]
        return None

    def register_migration(self, version, migration):
        """Register a migration map."""
        self.migrations.append((version, migration))

    def preform_migrations(self):
        """Perform all preflight checks."""
        if not self.migration_tracker:
            if self.sql_lite_migration.should_migrate():
                self.sql_lite_migration.migrate()
                self.sql_lite_migration.rename_db()
            version = str(self.tcex.app.ij.model.program_version)
            self.migration_tracker = VersionManagerModel(version=version)
            self.db.save(self.migration_tracker)
            return
        sorted_migrations = sorted(self.migrations, key=lambda x: parse(x[0]))
        for migration_version, migration in sorted_migrations:
            if parse(migration_version) < parse(self.migration_tracker.version):
                self.log.info(f'Skipping migration {migration_version}')
            else:
                self.log.info(f'Performing migration {migration_version}')
                migration(self.migration_tracker, self.db)
