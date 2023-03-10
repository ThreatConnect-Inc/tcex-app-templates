"""Database Schema Definition"""
# third-party
import arrow
from more import Base
from schema.arrow_date_time import ArrowDateTime
from sqlalchemy import Column, Integer, String


class ReportPdfTrackerSchema(Base):
    """Database Schema Definition"""

    __tablename__ = 'report_pdf_tracker'

    id = Column(Integer, primary_key=True)
    # xid = Column(String, nullable=False)  # report XID
    attempt_count = Column(Integer, default=0)
    attempt_result = Column(String, default='pending')  # failed, pending, success
    date_last_attempt = Column(ArrowDateTime, default=arrow.utcnow, onupdate=arrow.utcnow)
