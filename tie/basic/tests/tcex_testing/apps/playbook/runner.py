"""AppRunner — executes a playbook app in-process using KeyValueMock."""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from tcex import TcEx
from tcex.app.key_value_store.key_value_mock import KeyValueMock
from tcex_testing.apps.playbook.result import AppResult

# App ID used in output variable keys (matches KVStore convention)
_OUTPUT_APP_ID = '9876'


class AppRunner:
    """Runs a playbook app in-process using TcEx's built-in KeyValueMock.

    No Redis or fakeredis needed. KeyValueMock stores everything in a ClassVar
    dict keyed by context. Binary inputs are replaced with fake variable refs
    and pre-populated in contents_resolved so tcex skips the KV read path.
    """

    def __init__(self, app_dir: Path, output_dir: Path) -> None:
        self.app_dir = Path(app_dir)
        self.output_dir = Path(output_dir)
        self._variable_map = self._load_variable_map()

    def run(self, inputs: dict[str, Any], sdk: Any = None) -> AppResult:
        """Run the app with the given inputs dict and optional SDK instance."""
        context = str(uuid4())

        # build full inputs, replacing binary values with fake refs
        binary_values, full_inputs = self._build_inputs(inputs, context)

        # create output directories
        for key in ('tc_out_path', 'tc_in_path', 'tc_log_path', 'tc_temp_path'):
            Path(full_inputs[key]).mkdir(parents=True, exist_ok=True)

        # TcEx uses module-level singletons (registry, cached_property, scoped_property)
        # that persist across instances in the same process. Reset them so state from a
        # previous test run doesn't leak into this one.
        self._reset_tcex_state()

        # If set, TcEx loads app inputs from an encrypted platform file instead of
        # the config= dict we pass — silently ignoring our test inputs. Clear both
        # vars so TcEx always uses the config we provide.
        os.environ.pop('TC_APP_PARAM_KEY', None)
        os.environ.pop('TC_APP_PARAM_FILE', None)

        # Ensure TcEx writes null to KeyValueMock for output variables the app didn't set.
        # Without this, unset outputs are absent from the store and indistinguishable
        # from undeclared variables, making result.output(name) unreliable.
        os.environ.pop('TC_PLAYBOOK_WRITE_NULL', None)
        os.environ['TC_PLAYBOOK_WRITE_NULL'] = 'true'

        # clear KeyValueMock data from any previous run
        if 'tcex.app.key_value_store.key_value_mock' in sys.modules:
            sys.modules['tcex.app.key_value_store.key_value_mock'].KeyValueMock.data.clear()

        exit_code = 0
        exit_message = None

        try:
            from run import Run  # noqa: PLC0415

            run = Run()
            Run.setup()

            tcex = TcEx(config=full_inputs)

            # pre-populate contents_resolved so tcex skips the KV read path for inputs.
            # binary inputs are represented as fake ref strings in full_inputs (which
            # pydantic accepts as strings, matching platform behavior). we now replace
            # those fake ref strings in the resolved cache with the actual bytes values.
            resolved = tcex.inputs.contents.copy()
            resolved.update(binary_values)
            tcex.inputs.__dict__['contents_resolved'] = dict(sorted(resolved.items()))

            # inject tcex into Run, preempting its cached_property
            run.__dict__['tcex'] = tcex

            if sdk is not None:
                run.sdk = sdk

            try:
                run.launch()
                run.teardown()
            finally:
                self._reset_tcex_state()

        except SystemExit as e:
            exit_code = int(e.code) if e.code is not None else 0

        msg_path = Path(full_inputs['tc_out_path']) / 'message.tc'
        if msg_path.is_file():
            exit_message = msg_path.read_text(encoding='utf-8')

        outputs = self._read_outputs(context)
        return AppResult(exit_code=exit_code, exit_message=exit_message, outputs=outputs)

    def _build_inputs(
        self, inputs: dict[str, Any], context: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Build the full inputs dict and extract binary values for pre-population.

        Returns (binary_values, full_inputs) where:
          - binary_values: {param_name: actual_bytes} for pre-populating contents_resolved
          - full_inputs: complete config dict with binary values replaced by fake refs
        """
        out_vars = [v['key'] for v in self._variable_map.values()]
        test_dir = self.output_dir / context

        full = {
            'tc_kvstore_type': 'Mock',
            'tc_kvstore_host': 'localhost',
            'tc_kvstore_port': 6379,
            'tc_playbook_kvstore_id': 0,
            'tc_playbook_kvstore_context': context,
            'tc_playbook_out_variables': out_vars,
            # Fall back to placeholders so mock/unit runs work without TC credentials.
            # Tests that stage real TC objects must set these in the environment.
            'tc_api_access_id': os.environ.get('TC_API_ACCESS_ID', 'testing'),
            'tc_api_secret_key': os.environ.get('TC_API_SECRET_KEY', 'testing'),
            'tc_api_path': os.environ.get('TC_API_PATH', 'https://localhost:8443/api'),
            'tc_api_default_org': os.environ.get('TC_OWNER', 'TestOrg'),
            'tc_log_level': 'warning',
            'tc_log_to_api': False,
            'tc_log_path': str(test_dir / 'log'),
            'tc_out_path': str(test_dir / 'out'),
            'tc_in_path': str(test_dir / 'in'),
            'tc_temp_path': str(test_dir / 'tmp'),
        }

        binary_values: dict[str, Any] = {}
        for key, value in inputs.items():
            if isinstance(value, (bytes, bytearray)):
                # replace with a fake playbook variable ref string (pydantic accepts this
                # as a string, which matches what the platform sends for binary fields)
                fake_ref = f'#TestHarness:0:{key}!Binary'
                full[key] = fake_ref
                binary_values[key] = value
            else:
                full[key] = value
                binary_values[key] = value

        return binary_values, full

    def _read_outputs(self, context: str) -> dict[str, Any]:
        """Read all output variables from KeyValueMock after the run."""
        context_data = KeyValueMock.data.get(context, {})
        outputs: dict[str, Any] = {}

        for name, meta in self._variable_map.items():
            full_key = meta['key']
            var_type = meta['type']
            raw = context_data.get(full_key)
            if raw is None:
                outputs[name] = None
                continue

            if isinstance(raw, bytes):
                raw = raw.decode('utf-8')

            data = json.loads(raw)
            outputs[name] = self._deserialize(data, var_type)

        return outputs

    def _deserialize(self, data: Any, var_type: str) -> Any:
        type_lower = var_type.lower()
        if type_lower == 'binary':
            if data is None:
                return None
            return base64.b64decode(data)
        if type_lower == 'binaryarray':
            if data is None:
                return None
            return [base64.b64decode(item) if item is not None else None for item in data]
        if type_lower == 'string':
            return str(data) if data is not None else None
        if type_lower == 'stringarray':
            if data is None:
                return None
            return [str(item) if item is not None else None for item in data]
        return data

    def _load_variable_map(self) -> dict[str, dict[str, str]]:
        """Parse install.json outputVariables into {name: {key, type}} map."""
        install_json = self.app_dir / 'install.json'
        with install_json.open() as f:
            install = json.load(f)

        variable_map: dict[str, dict[str, str]] = {}
        for var in install.get('playbook', {}).get('outputVariables', []):
            name = var['name']
            var_type = var['type']
            variable_map[name] = {
                'key': f'#App:{_OUTPUT_APP_ID}:{name}!{var_type}',
                'type': var_type,
            }
        return variable_map

    @staticmethod
    def _reset_tcex_state() -> None:
        if 'tcex.registry' in sys.modules:
            sys.modules['tcex.registry'].registry._reset()
        if 'tcex.pleb.cached_property' in sys.modules:
            sys.modules['tcex.pleb.cached_property'].cached_property._reset()
        if 'tcex.pleb.scoped_property' in sys.modules:
            sys.modules['tcex.pleb.scoped_property'].scoped_property._reset()
