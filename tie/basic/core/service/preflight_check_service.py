"""ThreatConnect Preflight Check Service"""

import logging

from tcex import TcEx
from tcex.logger.trace_logger import TraceLogger

from core.app.enums import PREFLIGHT_CHECKS
from core.service.attribute_checker import AttributeChecker
from core.service.current_running_process import CurrentRunningProcess

logger = logging.getLogger('tcex')


class PreflightCheckService:
    """Service for performing preflight checks."""

    def __init__(self, tcex):
        """Initialize class properties."""
        self.tcex: TcEx = tcex
        self.log: TraceLogger = logger
        self.mapping = {
            PREFLIGHT_CHECKS.FILESYSTEM: self._check_filesystem,
            PREFLIGHT_CHECKS.TC_API: self._check_tc_api,
            PREFLIGHT_CHECKS.ATTRIBUTES: self._check_attributes,
            PREFLIGHT_CHECKS.DUPLICATE_PROCESSES_RUNNING: self._check_duplicate_service,
        }
        self.preflight_checks = set()

    def register_preflight_check(self, check):
        """Register a preflight check."""
        self.preflight_checks.add(check)

    def perform_checks(self):
        """Perform all preflight checks."""
        for preflight_check in self.preflight_checks:
            preflight_check()

    def _check_filesystem(self):
        """Check the filesystem for required conditions."""
        preflight_check_file = self.tcex.inputs.model.tc_out_path / 'preflight'
        try:
            preflight_check_file.write_text('preflight check')
            self.log.info(
                'action=check_filesystem, '
                'message=Preflight check for filesystem passed, '
                f'file={preflight_check_file}'
            )
        except Exception as ex:
            self.log.exception(
                'action=check_filesystem, message=Preflight check for filesystem failed, '
            )
            ex_msg = 'Preflight check for filesystem failed.'
            raise RuntimeError(ex_msg) from ex

    def _check_tc_api(self):
        """Check the ThreatConnect API for required conditions."""
        try:
            owners = self.tcex.api.tc.v3.security.owners()
            owners = [o.model.name for o in owners]
            self.log.info(
                f'action=check_tc_api, message=Preflight check for TC API passed, owners={owners}'
            )
        except Exception as ex:
            self.log.exception('action=check_tc_api, message=Preflight check for TC API failed.')
            ex_msg = 'Preflight check for TC API failed.'
            raise RuntimeError(ex_msg) from ex

    def _check_attributes(self):
        """Check the attributes for required conditions."""
        attribute_checker = AttributeChecker(self.tcex)
        is_valid = attribute_checker.is_valid()
        if is_valid:
            self.log.info('action=check_attributes, message=Preflight check for attributes passed.')
        else:
            self.log.error(
                'action=check_attributes, message=Preflight check for attributes failed.'
            )
            ex_msg = 'Preflight check for attributes failed. See logs for details.'
            raise RuntimeError(ex_msg)

    def _check_duplicate_service(self):
        """Check for duplicate services and shutdown all services if found."""
        current_running_processes = CurrentRunningProcess(self.tcex)
        current_running_processes.load()

        if current_running_processes.should_write():
            current_running_processes.write()
        else:
            current_running_processes.file.unlink()
            current_running_processes.shutdown_existing_service()
