"""CurrentRunningProcess for process management and duplicate service detection.

This module provides functionality to track running processes and detect duplicate services
to prevent conflicts in the TCEX environment.
"""

import json
import os

import psutil
from tcex import TcEx


class CurrentRunningProcess:
    """CurrentRunningProcess for process management and duplicate service detection.

    This class manages running processes, tracks session IDs, and provides functionality
    to detect and handle duplicate services to prevent conflicts.

    Usage:
        tcex = TcEx()
        process_manager = CurrentRunningProcess(tcex)
        process_manager.load()
        if process_manager.should_write():
            process_manager.write()
    """

    def __init__(self, tcex: TcEx) -> None:
        """Initialize class properties.

        Args:
            tcex: TCEX instance for accessing inputs and services
        """
        self.tcex = tcex
        self.pid = os.getpid()
        self.session_id = self.tcex.inputs.model.tc_out_path.parent.name
        self.file = self.tcex.inputs.model.tc_out_path / 'process_data.json'
        self.topic = self.tcex.inputs.model.tc_svc_server_topic
        self.existing_data: dict = {}

    def load(self) -> None:
        """Load existing process data from file."""
        if not self.file.is_file():
            self.existing_data = {}
        else:
            try:
                self.existing_data = json.loads(self.file.read_text())
            except Exception as ex:
                ex_msg = 'Failed to load existing process data'
                raise RuntimeError(ex_msg) from ex

    def write(self) -> None:
        """Write current process data to file."""
        with self.file.open('w') as fh:
            json.dump(self.as_dict(), fh, indent=4)

    def should_write(self) -> bool:
        """Check if process data should be written.

        Returns:
            True if process data should be written, False otherwise
        """
        pid = self.existing_data.get('pid')
        if not pid:
            return True
        try:
            proc = psutil.Process(pid)
            cmd_line = ' '.join(proc.cmdline())
            if self.session_id not in cmd_line:
                return True
        except psutil.NoSuchProcess:
            return True
        return False

    def shutdown_existing_service(self, topic: str | None = None) -> None:
        """Shutdown existing service to prevent conflicts.

        Args:
            topic: Topic to use for shutdown message, defaults to existing topic

        Raises:
            RuntimeError: If no topic is available or during shutdown process
        """
        topic = topic or self.existing_data.get('topic')
        if not topic:
            ex_msg = 'No topic provided/available for existing service shutdown.'
            raise RuntimeError(ex_msg)
        self.tcex.app.service.message_broker.publish(
            message=json.dumps(
                {
                    'command': 'Shutdown',
                    'reason': 'Duplicate service detected',
                }
            ),
            topic=topic,
        )
        ex_msg = 'Preflight check for duplicate service.'
        raise RuntimeError(ex_msg)

    def as_dict(self) -> dict:
        """Convert process data to dictionary format.

        Returns:
            Dictionary containing process ID and topic information
        """
        return {
            'pid': self.pid,
            'topic': self.topic,
        }
