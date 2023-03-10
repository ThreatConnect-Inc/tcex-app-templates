"""Database Schema Definition"""
# third-party
from schema.arrow_date_time import ArrowDateTime
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.hybrid import hybrid_property

from .job_request_base_schema import JobRequestBaseSchema


class JobRequestSchema(JobRequestBaseSchema):
    """Database Schema Definition"""

    # track count for metrics and reporting
    count_batch_error = Column(Integer, default=0)
    count_batch_group_success = Column(Integer, default=0)
    count_batch_indicator_success = Column(Integer, default=0)
    count_download_group = Column(Integer, default=0)
    count_download_indicator = Column(Integer, default=0)

    # track start and complete time of task for metrics and reporting
    date_convert_start = Column(ArrowDateTime, nullable=True)
    date_convert_complete = Column(ArrowDateTime, nullable=True)
    date_download_start = Column(ArrowDateTime, nullable=True)
    date_download_complete = Column(ArrowDateTime, nullable=True)
    date_upload_start = Column(ArrowDateTime, nullable=True)
    date_upload_complete = Column(ArrowDateTime, nullable=True)

    # task settings
    last_modified_filter_start = Column(ArrowDateTime, nullable=False)
    last_modified_filter_end = Column(ArrowDateTime, nullable=False)
    group_types = Column(String, nullable=True)
    indicator_types = Column(String, nullable=True)

    @hybrid_property
    def convert_runtime(self):
        """Return timedelta"""
        if self.date_convert_start and self.date_convert_complete:
            return self.date_convert_complete - self.date_convert_start
        return None

    @hybrid_property
    def download_runtime(self):
        """Return timedelta"""
        if self.date_download_start and self.date_download_complete:
            return self.date_download_complete - self.date_download_start
        return None

    @hybrid_property
    def upload_runtime(self):
        """Return timedelta"""
        if self.date_upload_start and self.date_upload_complete:
            return self.date_upload_complete - self.date_upload_start
        return None

    @hybrid_property
    def total_runtime(self):
        """Return timedelta"""
        if self.convert_runtime and self.download_runtime and self.upload_runtime:
            return self.convert_runtime + self.download_runtime + self.upload_runtime
        return None
