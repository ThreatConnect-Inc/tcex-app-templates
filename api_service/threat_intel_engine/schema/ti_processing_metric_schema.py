"""Database Schema Definition"""
# third-party
import arrow
from more import Base
from schema.arrow_date_time import ArrowDateTime
from sqlalchemy import Column, Integer, String


class TiProcessingMetricSchema(Base):
    """Database Schema Definition"""

    __tablename__ = 'ti_processing_metric_schema'

    id = Column(Integer, primary_key=True)
    date_last_updated = Column(ArrowDateTime, default=arrow.utcnow, onupdate=arrow.utcnow)
    ti_type = Column(String(100), nullable=False, unique=True)
    ti_count = Column(Integer, default=0, nullable=False)
