"""UIConfigBuilder concrete implementation for building UI configurations."""

from core.api.ui_config_builder_abc import UIConfigBuilderABC
from core.service.notification_service import NOTIFICATION_TYPES


class UIConfigBuilder(UIConfigBuilderABC):
    """Concrete implementation of UIConfigBuilderABC for building UI configurations."""

    def adhoc_request_fields(self):
        """Generate fields for the Ad-Hoc Request form."""
        return [
            self.generate_form_field(
                name='start_time',
                label='Start Time',
                type_='date',
                required=True,
                info='Start time must be less than end time.',
                additional_validators=[{'name': 'gt', 'config': {'field': 'start_time'}}],
            ),
            self.generate_form_field(
                name='end_time',
                label='End Time',
                type_='date',
                required=True,
                info='End time must be greater than start time.',
                additional_validators=[{'name': 'gt', 'config': {'field': 'start_time'}}],
            ),
            self.generate_form_field(
                name='sample_types',
                label='Sample Types',
                type_='multi-select',
                info='Select the sample types to include in the request.',
                choices=self.settings.all_sample_types,
                default=list(self.settings.app_settings.sample_types),
                required=True,
            ),
        ]

    def download_ti_fields(self):
        """Generate fields for the Download TI form."""
        return [
            self.generate_form_field(
                name='sample_types',
                label='Sample Types',
                type_='select',
                choices=self.settings.all_sample_types,
                default='Event',
                required=True,
            ),
            self.generate_form_field(name='external_id', label='External ID', required=True),
        ]

    def job_table_columns(self):
        """Generate columns for the Job Table."""
        return [
            self.generate_field('requestId', 'Job ID'),
            self.generate_field('jobType', 'Job Type'),
            self.generate_field('pipeline', 'Pipeline'),
            self.generate_field('countDownloadGroup', 'Groups Downloaded'),
            self.generate_field('countBatchGroupSuccess', 'Groups Uploaded'),
            self.generate_field('countDownloadIndicator', 'Indicators Downloaded'),
            self.generate_field('countBatchIndicatorSuccess', 'Indicators Uploaded'),
            self.generate_field('startTime', 'Start Time', 'date'),
            self.generate_field('endTime', 'End Time', 'date'),
            self.generate_field('status', 'Status', 'status'),
        ]

    def job_table_details(self):
        """Generate details for the Job Table."""
        return [
            self.generate_field('requestId', 'Job ID'),
            self.generate_field('jobType', 'Job Type'),
            self.generate_field('taskType', 'Task Type'),
            self.generate_field('groupTypes', 'Group Types', 'array'),
            self.generate_field('indicatorTypes', 'Indicator Types', 'array'),
            self.generate_field('status', 'Status'),
            self.generate_field('dateQueued', 'Date Queued', 'date'),
            self.generate_field('dateStarted', 'Date Started', 'date'),
            self.generate_field('dateDownloadStart', 'Date Download Start', 'date'),
            self.generate_field('dateDownloadComplete', 'Date Download Complete', 'date'),
            self.generate_field('downloadRuntime', 'Download Runtime'),
            self.generate_field('dateConvertStart', 'Date Convert Start', 'date'),
            self.generate_field('dateConvertComplete', 'Date Convert Complete', 'date'),
            self.generate_field('convertRuntime', 'Convert Runtime'),
            self.generate_field('dateUploadStart', 'Date Upload Start', 'date'),
            self.generate_field('dateUploadComplete', 'Date Upload Complete', 'date'),
            self.generate_field('uploadRuntime', 'Upload Runtime'),
            self.generate_field('dateCompleted', 'Date Completed', 'date'),
            self.generate_field('totalRuntime', 'Total Runtime'),
            self.generate_field('totalRetryCount', 'Total Retries'),
            self.generate_field('countDownloadGroup', 'Count Downloaded Groups'),
            self.generate_field('countBatchGroupSuccess', 'Count Batch Group Success'),
            self.generate_field('countDownloadIndicator', 'Count Downloaded Indicators'),
            self.generate_field('countBatchIndicatorSuccess', 'Count Batch Indicator Success'),
            self.generate_field('countBatchError', 'Count Batch Error'),
            self.generate_field('dateFailed', 'Date Failed', 'date'),
        ]

    def job_table_filters(self):
        """Generate filters for the Job Table."""
        return [
            self.generate_form_field(name='requestId', label='Job ID'),
            self.generate_form_field(
                name='jobType',
                label='Job Type',
                type_='multi-select',
                choices=['Scheduled', 'Ad-Hoc'],
                default=['Scheduled', 'Ad-Hoc'],
            ),
            self.generate_form_field(
                name='status',
                label='Status',
                type_='multi-select',
                choices=self.all_statuses,
                default=self.all_statuses,
                min_width=250,
            ),
        ]

    def notification_table_columns(self):
        """Generate columns for the Notification Table."""
        return [
            self.generate_field('dateAdded', 'Date', 'date'),
            self.generate_field('category', 'Category', 'category'),
            self.generate_field('priority', 'Priority'),
            self.generate_field('message', 'Message'),
            self.generate_field('sendStatus', 'Send Status', 'send-status'),
        ]

    def notification_table_details(self):
        """Generate details for the Notification Table."""
        return [
            self.generate_field('id', 'ID'),
            self.generate_field('dateAdded', 'Date', 'date'),
            self.generate_field('category', 'Category', 'category'),
            self.generate_field('notificationType', 'Notification Type'),
            self.generate_field('priority', 'Priority'),
            self.generate_field('message', 'Message'),
            self.generate_field('jobIds', 'Job IDs', 'array'),
            self.generate_field('sendStatus', 'Send Status', 'send-status'),
            self.generate_field('sendStatusCode', 'Status Code'),
            self.generate_field('sendStatusText', 'Status Text'),
            self.generate_field('apiRequest', 'API Request', 'json'),
            self.generate_field('apiResponse', 'API Response', 'json'),
        ]

    def notification_table_filters(self):
        """Generate filters for the Notification Table."""
        return [
            self.generate_form_field(
                name='category',
                label='Category',
                type_='multi-select',
                choices=list(NOTIFICATION_TYPES.keys()),
                default=list(NOTIFICATION_TYPES.keys()),
            ),
            self.generate_form_field(
                name='priority',
                label='Priority',
                type_='multi-select',
                choices=['Low', 'Medium', 'High'],
                default=['Low', 'Medium', 'High'],
            ),
            self.generate_form_field(
                name='send_status',
                label='Send Status',
                type_='multi-select',
                choices=['Success', 'Failed', 'Not Sent'],
                default=['Success', 'Failed', 'Not Sent'],
            ),
        ]

    @property
    def notifications_enabled(self) -> bool:
        """Return True if notifications are configured (digest interval is set)."""
        return self.settings.app_settings.notification_digest_interval is not None

    def side_nav(self):
        """Generate the side navigation items."""
        # The order of the items in this list determines the order of the side nav.
        items = [
            self.generate_side_nav_item(label='Dashboard', path='dashboard'),
            self.generate_side_nav_item(label='Jobs', path='jobs'),
            self.generate_side_nav_item(label='Tasks', path='tasks'),
            self.generate_side_nav_item(label='Download', path='download'),
            self.generate_side_nav_item(label='Batch Errors', path='batchErrors'),
        ]

        if self.notifications_enabled:
            items.append(self.generate_side_nav_item(label='Notifications', path='notifications'))

        items.append(
            self.generate_side_nav_item(label='Attachment Status', path='reportPdfTrackers')
        )
        items.append(self.generate_side_nav_item(label='Documentation', path='documentation'))
        items.append(self.generate_side_nav_item(label='Settings', path='settings'))
        return items

    # ------------------------------------------------------------------
    # Settings page / onboarding stepper
    # ------------------------------------------------------------------

    def connection_inputs(self):
        """Where this engine is pointed. Read-only — deploy-time configuration.

        Both come from the app inputs and neither is on `AppSettings`, so a payload
        carrying them is dropped by `build_candidate` regardless of what the form posts.
        `disabled=True` is a UI affordance only; the model is what actually protects them.

        Both use `description` rather than `info`, which means the prose is always visible
        and there is no ⓘ on either field. Deliberate: this is the only section rendered
        while onboarding is incomplete, so it is the first thing a new operator reads, and
        text that explains a read-only value should not be hidden behind an icon.
        """
        return [
            self.generate_settings_input(
                name='api_url',
                label='Service URL',
                default=self.settings.api_url,
                disabled=True,
                description=(
                    'The vendor endpoint this engine reads from — the URL entered in the '
                    'Feed Deployer when the app was deployed. To point the engine '
                    'somewhere else, redeploy the app.'
                ),
            ),
            self.generate_settings_input(
                name='api_key',
                label='API Key',
                # The MASK, never the key. This is served in `GET /api/tc/app-config`, so
                # anything put here reaches the browser, devtools, and any HAR attached to
                # a support ticket. The last two characters are enough to tell which key is
                # deployed; the key itself has no reason to leave the server.
                default=self.mask_secret(self.settings.api_key),
                disabled=True,
                description=(
                    'Only the last two characters are shown, so you can confirm which key '
                    'is in use without exposing it. To replace or rotate the key, redeploy '
                    'the app with the new value.'
                ),
            ),
        ]

    def ingestion_inputs(self):
        """Settings governing what this engine pulls from the vendor.

        The EXAMPLE app-specific section. Each field's `name` must match a field on
        `AppSettings` — that pairing is the whole of the wiring, and a name with no
        matching field is silently dropped on save by `build_candidate`.
        """
        choices, selected = self.select_choices(
            self.settings.all_sample_types, self.settings.app_settings.sample_types
        )
        return [
            self.generate_settings_input(
                name='sample_types',
                label='Sample Types',
                type_='multi-select',
                min_width=320,
                # Set `searchable=True` for a list long enough that scanning beats typing.
                # A handful of options in a curated order is quicker to read than to filter.
                choices=choices,
                default=selected,
                short_text='Restrict ingestion to these object types.',
                description=(
                    'Leave every option unselected to ingest everything this deployment '
                    'can see. Fewer types means fewer requests against the vendor rate '
                    'limit and faster jobs.'
                ),
            ),
        ]

    @property
    def notification_labels(self) -> tuple[str, ...]:
        """Narrow the inherited list to the categories `app_spec.yml` offers.

        The other `NOTIFICATION_TYPES` categories are internal and not admin-selectable
        for this app.
        """
        return ('App Startup', 'Job Retrying', 'Job Failed', 'Job Recovered')

    def advanced_settings_inputs(self):
        """Scheduling and retry settings. Defaults are tuned for normal operation."""
        advanced = self.settings.app_settings
        return [
            self.generate_settings_input(
                name='frequency',
                label='Poll Frequency (hours)',
                type_='number',
                required=True,
                additional_validators=[
                    {'name': 'gte', 'config': {'value': 1}},
                    {'name': 'lte', 'config': {'value': 168}},
                ],
                default=advanced.frequency,
                short_text='How often a new ingestion job is queued.',
                description=(
                    'Each job asks the vendor for everything published since the previous '
                    'job, so a longer interval means larger, less frequent batches rather '
                    'than missed data. Accepts 1 to 168 hours. Keep it well below the '
                    'Failure Threshold — a threshold shorter than two poll intervals marks '
                    'healthy jobs as failed.'
                ),
            ),
            self.generate_settings_input(
                name='failure_threshold',
                label='Failure Threshold (hours)',
                type_='number',
                required=True,
                additional_validators=[
                    {'name': 'gte', 'config': {'value': 1}},
                    {'name': 'lte', 'config': {'value': 720}},
                ],
                # Stored as a timedelta, edited in whole hours. The posted value is read
                # back by `AppSettingsBase.parse_failure_threshold`.
                default=int(advanced.failure_threshold.total_seconds() // 3600),
                short_text='How long a job may run before it is treated as failed.',
                description=(
                    'A job still running after this many hours is marked failed and '
                    'retried. Accepts 1 to 720 hours. Set it comfortably above the Poll '
                    'Frequency — a threshold shorter than two poll intervals fails jobs '
                    'that are simply still working.'
                ),
            ),
            self.generate_settings_input(
                name='max_retries',
                label='Maximum Retries',
                type_='number',
                required=True,
                additional_validators=[
                    {'name': 'gte', 'config': {'value': 0}},
                    {'name': 'lte', 'config': {'value': 100}},
                ],
                default=advanced.max_retries,
                short_text='How many times a failed job is retried before it is abandoned.',
                description=(
                    'Once a job has used all its retries it stops for good and raises a Job '
                    'Failed notification. Accepts 0 to 100; set 0 to stop retrying failed '
                    'jobs altogether. A higher value rides out longer vendor outages, a '
                    'lower one surfaces a persistent problem sooner.'
                ),
            ),
            self.generate_settings_input(
                name='backfill',
                label='Initial Backfill (hours)',
                type_='number',
                required=True,
                additional_validators=[
                    {'name': 'gte', 'config': {'value': 1}},
                    {'name': 'lte', 'config': {'value': 8760}},
                ],
                default=advanced.backfill,
                short_text='How much history the very first run reaches back for.',
                description=(
                    'Only used when there is no previous job — after that each run resumes '
                    'from where the last one ended, so changing this later has no effect on '
                    'an engine that is already running. Accepts 1 to 8760 hours (one year). '
                    'The window is split into jobs of Backfill Chunk Size, so a large value '
                    'with a small chunk size queues a great many jobs at once.'
                ),
            ),
            self.generate_settings_input(
                name='backfill_frequency',
                label='Backfill Chunk Size (hours)',
                type_='number',
                required=True,
                additional_validators=[
                    {'name': 'gte', 'config': {'value': 1}},
                    {'name': 'lte', 'config': {'value': 168}},
                ],
                default=advanced.backfill_frequency,
                short_text='The largest time span a single job is allowed to cover.',
                description=(
                    'Any range longer than this is divided into consecutive jobs — both the '
                    'initial backfill and an ordinary catch-up after downtime. Accepts 1 to '
                    '168 hours. Smaller chunks mean more, smaller requests to the vendor, '
                    'which is gentler on rate limits but slower to work through a backlog.'
                ),
            ),
        ]

    def settings_form(self):
        """Connection first — what the engine is pointed at, before what it does with it.

        Ingestion leads the editable sections: it is what an operator came to change.
        """
        return [
            {
                'name': 'Connection',
                'description': (
                    'Set in the Feed Deployer when this app was deployed. Shown read-only '
                    'so you can confirm what the engine is using — to change either value, '
                    'redeploy the app.'
                ),
                # Nothing here is editable, so it has no place in a setup flow — the
                # stepper collects decisions, and these are not decisions.
                'stepper': False,
                'fields': self.connection_inputs(),
            },
            {
                'name': 'Ingestion',
                'description': (
                    'Controls what this engine ingests, and how much related context is '
                    'brought in with it.'
                ),
                'fields': self.ingestion_inputs(),
            },
            {
                'name': 'Notifications',
                'description': (
                    'Controls which events about this engine are sent to the ThreatConnect '
                    'notification center, and how often. Every event is recorded on the '
                    'Notifications page in this app whether or not it is sent.'
                ),
                'fields': self.notification_inputs(),
            },
            {
                'name': 'Advanced Settings',
                # `warning`, not `description` — this is telling an operator NOT to change
                # things, which a muted line under a heading does not convey.
                'warning': (
                    'These defaults suit most deployments. Change them only for a specific '
                    'reason — a vendor rate limit, an extended outage to ride out, or a '
                    'recommendation from ThreatConnect support.'
                ),
                'fields': self.advanced_settings_inputs(),
            },
        ]

    def populate(self):
        """Build the complete UI configuration."""
        config = {
            'global': {'sideNav': self.side_nav()},
            # `settings_form()` pairs the settings this app declares on `AppSettings` with
            # the section headings and prose the Settings page and onboarding stepper
            # render. `core/api/endpoint/tc_app_config.py` declares `UiModel` and
            # `AppConfig` with `extra=Extra.allow`, so a new top-level key here needs no
            # schema change.
            'settingsForm': self.settings_form(),
            'jobTable': {
                'columns': self.job_table_columns(),
                'details': self.job_table_details(),
                'filters': {'fields': self.job_table_filters()},
            },
            'downloadTI': {
                'form': {
                    'fields': self.download_ti_fields(),
                },
            },
            'adhocRequest': {
                'form': {
                    'fields': self.adhoc_request_fields(),
                },
            },
        }

        if self.notifications_enabled:
            config['notifications'] = {
                'columns': self.notification_table_columns(),
                'details': self.notification_table_details(),
                'filters': {'fields': self.notification_table_filters()},
            }

        return config
