"""UIConfigBuilder concrete implementation for building UI configurations."""

# first-party
from core.api.ui_config_builder_abc import UIConfigBuilderABC


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
                default=list(self.settings.sample_types),
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

    def side_nav(self):
        """Generate filters for the Job Table."""
        # The order of the items in this list determines the order of the side nav.
        return [
            self.generate_side_nav_item(label='Dashboard', path='dashboard'),
            self.generate_side_nav_item(label='Jobs', path='jobs'),
            self.generate_side_nav_item(label='Tasks', path='tasks'),
            self.generate_side_nav_item(label='Download', path='download'),
            self.generate_side_nav_item(label='Batch Errors', path='batchErrors'),
            self.generate_side_nav_item(label='Attachment Status', path='reportPdfTrackers'),
        ]

    def populate(self):
        """Build the complete UI configuration."""
        return {
            'global': {'sideNav': self.side_nav()},
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
