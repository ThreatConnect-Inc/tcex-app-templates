"""Supervisor Module - Runtime failure handling with backoff and staleness-based shutdown."""

# first-party
from core.supervisor.config import SupervisorConfigModel
from core.supervisor.supervisor import Supervisor

__all__ = ['Supervisor', 'SupervisorConfigModel']
