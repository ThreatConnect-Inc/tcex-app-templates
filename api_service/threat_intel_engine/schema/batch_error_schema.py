"""Database Schema Definition"""
# third-party
import arrow
from more import Base
from schema.arrow_date_time import ArrowDateTime
from sqlalchemy import Column, ForeignKey, Integer, String, Text


class BatchErrorSchema(Base):
    """Database Schema Definition"""

    __tablename__ = 'batch_error'

    id = Column(Integer, primary_key=True)
    code = Column(String(10))
    date_added = Column(ArrowDateTime, default=arrow.utcnow)
    message = Column(String)
    reason = Column(Text)
    request_id = Column(String, ForeignKey('job_request.request_id', ondelete='CASCADE'))
