"""Define custom settings for app.

THE STORAGE PATH IS DERIVED FROM THIS MODULE PATH AND CLASS NAME.
`core/json_db/json_db.py` builds the storage directory from `f'{module}.{ClassName}'`,
so moving or renaming this module — or the `AppSettings` class — orphans the saved record
and the app silently re-seeds from the app inputs on the next boot.

The parent `SettingModelBase`/`AppSettingsBase` classes should never be edited.
"""

import logging

from pydantic import Field

from core.model.settings_model_base import AppSettingsBase, SettingModelBase

logger = logging.getLogger('tcex')


class AppSettings(AppSettingsBase):
    """The settings an admin can edit, and the only thing written to the JSON DB.

    Flat, and named exactly as the settings form posts them — see `UIConfigBuilder`. That
    is what lets an update be a plain reconstruction with the payload merged over the top,
    with pydantic doing the validating and converting.

    `SettingModel` holds one of these and every reader goes through it, so the stored
    record and the live values are the same object — there is nothing to copy and nothing
    to keep in sync.

    Only the app-specific settings are declared here. `AppSettingsBase` contributes the
    ones every TIE app has — `frequency`, `failure_threshold`, `max_retries`,
    `max_batch_errors`, `notification_digest_interval`, `notification_types` — which is
    why `load()` below sets fields that do not appear in this file.

    `sample_types` is the EXAMPLE app-specific setting: replace it with whatever this app
    lets an admin change, and give the replacement a matching field on the settings form
    (`api/ui_config_builder.py::ingestion_inputs`) under the same name.
    """

    sample_types: list[str] = Field(default_factory=list)

    @classmethod
    def load(cls, db, inputs) -> 'AppSettings':
        """Return the stored settings, seeding from the app inputs on first boot.

        First boot has no record, so whatever the app inputs produced is written as the
        starting point — which is what keeps an existing deployment working unchanged
        after an upgrade. Every boot after that the stored record wins and the inputs for
        those fields are ignored, because an admin edits them in the UI rather than by
        redeploying.

        `inputs.advanced_settings` is the tcex key=value string input; it seeds the record
        and is then out of the picture. Anything that is NOT admin-editable (a value the
        form cannot express, for example) stays on the app inputs and is re-read on every
        boot rather than being copied in here.

        Call this from `app.py`::

            app_settings = AppSettings.load(self.db, self.model)

        and override `db_path` there to `self.model.tc_out_path / 'json_db'` — the core
        default derives it from `settings.base_path`, which would recurse
        `settings -> db -> db_path -> settings`.
        """
        try:
            return db.load(cls, cls.__fields__['id'].default)
        except FileNotFoundError:
            pass  # ordinary first boot — no record written yet
        except Exception as ex:
            # The record EXISTS but cannot be read: a .gz truncated by a disk-full write or
            # a container killed mid-save, a corrupt gzip header, invalid JSON, or a payload
            # the current schema rejects. `JsonDB.load()` has no invalid-JSON handling (only
            # `load_all` does), so these used to propagate — and `settings` is a
            # cached_property reached during app init, so an unreadable record stopped the
            # app booting instead of re-seeding, which is what the module docstring promises.
            #
            # Caught broadly on purpose. Enumerating types is what went wrong before: the
            # list read (OSError, ValueError), which covers BadGzipFile and JSONDecodeError
            # but NOT the EOFError a truncated gzip actually raises — so the one failure the
            # comment named was the one that still crashed the app. Re-seeding from app
            # inputs is the correct response to any unreadable record, whatever the type.
            logger.warning(
                f'event=app-settings-unreadable, action=reseeding-from-app-inputs, '
                f'error={type(ex).__name__}: {ex}'
            )

        advanced = inputs.advanced_settings
        record = cls(
            sample_types=sorted(inputs.sample_types or []),
            frequency=advanced.frequency,
            failure_threshold=advanced.failure_threshold,
            max_retries=advanced.max_retries,
            backfill=advanced.backfill,
            backfill_frequency=advanced.backfill_frequency,
            notification_digest_interval=inputs.notification_digest_interval,
            notification_types=inputs.notification_types,
        )
        db.save(record)
        return record


class SettingModel(SettingModelBase):
    """Custom Setting Model"""

    # Deploy-time configuration. Read from the app inputs on every boot and never
    # persisted, so a settings payload can never reach them — `build_candidate` drops any
    # key that is not declared on `AppSettings`. Shown read-only on the Settings page; see
    # `api/ui_config_builder.py::connection_inputs`.
    api_url: str = ''
    api_key: str = ''  # Extract from SecretStr before construction

    # The catalogue the `sample_types` setting picks from. Deploy-time, not editable.
    all_sample_types: list[str] = Field(default_factory=list)

    #: The persisted, admin-editable settings. REQUIRED, deliberately: the only correct
    #: value is the stored record, and `app.py` is what supplies it —
    #: `app_settings=AppSettings.load(self.db, self.model)`. A default here would let the
    #: App boot with an unwired, unsaved record, and the symptom of that is settings
    #: silently reverting on every restart. Failing construction instead turns a silent
    #: data-loss bug into an immediate, obvious one.
    app_settings: AppSettings
