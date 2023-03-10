"""Database Schema Definition"""
# third-party
import arrow
from more import Base
from schema.arrow_date_time import ArrowDateTime
from sqlalchemy import Column, String
from sqlalchemy.ext.hybrid import hybrid_property


class JobRequestBaseSchema(Base):
    """Database Schema Definition"""

    __tablename__ = 'job_request'

    date_completed = Column(ArrowDateTime, nullable=True)
    date_failed = Column(ArrowDateTime, nullable=True)
    date_queued = Column(ArrowDateTime, default=arrow.utcnow)
    date_started = Column(ArrowDateTime, nullable=True)
    job_type = Column(String)  # scheduled, backfill
    request_id = Column(String, primary_key=True)
    status = Column(String, default='pending')  # should match status in app.py:settings

    @hybrid_property
    def status_icon(self):
        """Return status icon for UI."""
        return 'question_mark'
