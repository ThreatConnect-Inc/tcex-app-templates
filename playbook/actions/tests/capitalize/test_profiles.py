"""TcEx App Testing Module"""
# standard library
import os
import warnings

# third-party
import pytest
from _pytest.config import Config
from _pytest.monkeypatch import MonkeyPatch
from tcex_app_testing.test_case import TestCasePlaybook

from .custom_feature import CustomFeature
from .validate_feature import ValidateFeature


# pylint: disable=no-member,too-many-function-args,useless-super-delegation
class TestProfiles(TestCasePlaybook):
    """TcEx App Testing Template."""

    @classmethod
    def setup_class(cls):
        """Run setup logic before all test cases in this module."""
        super().setup_class()
        cls.custom = CustomFeature()
        if os.getenv('SETUP_CLASS') is None:
            cls.custom.setup_class(cls)
        # enable auto-update of profile data
        cls.enable_update_profile = True

    def setup_method(self):
        """Run setup logic before test method runs."""
        super().setup_method()
        if os.getenv('SETUP_METHOD') is None:
            self.custom.setup_method(self)

    @classmethod
    def teardown_class(cls):
        """Run setup logic after all test cases in this module."""
        if os.getenv('TEARDOWN_CLASS') is None:
            cls.custom.teardown_class(cls)

        super().teardown_class()
        # disable auto-update of profile data
        cls.enable_update_profile = False

    def teardown_method(self):
        """Run teardown logic after test method completes."""
        if os.getenv('TEARDOWN_METHOD') is None:
            self.custom.teardown_method(self)
        super().teardown_method()

    def test_profiles(self, profile_name: str, monkeypatch: MonkeyPatch, pytestconfig: Config):
        """Run pre-created testing profiles."""
        # initialize profile
        self.aux.init_profile(
            app_inputs=self.app_inputs,
            monkeypatch=monkeypatch,
            profile_name=profile_name,
            pytestconfig=pytestconfig,
        )

        # run custom test method before run method
        self.custom.test_pre_run(
            self, self.aux.profile_runner.data, monkeypatch if self.run_method == 'inline' else None
        )

        assert self.run_profile() in self.aux.profile_runner.model.exit_codes

        # run custom test method before validation
        self.custom.test_pre_validate(self, self.aux.profile_runner.data)

        # get Validation instance
        validation = ValidateFeature(self.aux.validator)

        # validate App outputs and Profile outputs are consistent
        if self.aux.profile_runner.pytest_args_model.updated is True:
            msg = 'Profile was updated during this run. Please rerun test profile.'
            warnings.warn(msg)
            pytest.xfail(msg)
        elif self.aux.profile_runner.model.initialized is False:
            msg = 'Profile was not initialized during this run. Please rerun test profile.'
            warnings.warn(msg)
            pytest.xfail(msg)
        else:
            validation.validate_outputs(
                self.aux.profile_runner.tc_playbook_out_variables,
                self.aux.profile_runner.model.outputs,
            )

            # validate App outputs with Profile outputs
            validation.validate(self.aux.profile_runner.model.outputs)

            # validate exit message
            if self.aux.profile_runner.model.exit_message:
                self.aux.validate_exit_message(self.aux.profile_runner.model.exit_message)
