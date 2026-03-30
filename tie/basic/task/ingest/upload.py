"""Batch Submit"""

# standard library
import re
from functools import cached_property
from pathlib import Path

from tcex.api.tc.v2.batch import BatchSubmit

# first-party
from core.model.tie.task_setting_pipe_model import TaskSettingPipeModel
from core.task.upload_ingest_abc import UploadIngestABC, WriteTypes

# third-party
from model import JobRequestModel


# TODO: Fix spelling to be consistent
class Upload(UploadIngestABC):
    """Task Module for uploading data."""

    @property
    def write_type_mapping(self):
        """Write type mapping."""
        # This is how you would go about setting up a mapping for file names to write types.
        # return {
        #     r'*event*': WriteTypes(
        #             attribute='Singleton',
        #             tag='Replace',
        #             security_label='Replace'
        #         ),
        # }
        return {}

    def get_write_type(self, file_name: str) -> WriteTypes:
        """Get write type based on file name."""
        for pattern, write_type in self.write_type_mapping.items():
            if re.match(pattern, file_name):
                return write_type
        return WriteTypes(attribute='Replace', tag='Replace', security_label='Replace')

    def get_batch_cleaner(self, batch_submit: BatchSubmit):
        """Return a BatchCleaner for content cleaning during batch submit.

        The BatchCleaner runs cleaning steps on batch content before uploading
        to ThreatConnect. Configure by passing keyword arguments to
        batch_submit.cleaner():

            combine_on_filename: Merge File indicators sharing a fileOccurrence fileName.
            convert_to_mitre_tags: Convert tag names to formatted MITRE ATT&CK tags.
            convert_to_naics_tags: Convert tag names to formatted NAICS tags.
            deduplicate_indicators: Merge duplicate indicators (hash-overlap for Files).
            deduplicate_groups: Merge duplicate groups by xid.
            deduplicate_attributes: Remove duplicate attributes from indicators/groups.
            truncate_attributes: Truncate attribute values exceeding their type's maxSize.

        Example:
            return batch_submit.cleaner(
                deduplicate_indicators=True,
                truncate_attributes=True,
            )
        """
        return batch_submit.cleaner()

    def process_file(
        self, file: Path, request: JobRequestModel
    ) -> tuple[BatchSubmit, int] | tuple[None, None]:
        """Process batch file."""
        write_type = self.get_write_type(file.name)

        batch_submit = self.tcex.api.tc.v2.batch_submit(
            action='Create',
            owner=self.settings.tc_owner,
            tag_write_type=write_type.tag,
            security_label_write_type=write_type.security_label,
            attribute_write_type=write_type.attribute,
            playbook_triggers_enabled=True,
        )

        batch_id = self.create_job_batch(batch_submit)
        self.submit_batch(batch_submit, batch_id, file)
        status = self.poll_batch(batch_submit, batch_id)
        self.increment_counts(request, status)
        return batch_submit, batch_id

    @cached_property
    def task_settings(self) -> TaskSettingPipeModel:
        """Return the task settings."""
        name = 'Upload'
        if self.pipeline:
            name = f'{name} - {self.pipeline.title()}'
        return TaskSettingPipeModel(
            base_path=self.settings.base_path,
            date_field_start='date_upload_start',
            date_field_complete='date_upload_complete',
            description='Uploads the threat intel data into the ThreatConnect Platform.',
            max_execution_minutes=60,
            name=name,
            schedule_period=10,
            schedule_unit='seconds',
        )
