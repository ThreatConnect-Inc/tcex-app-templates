#!python3
"""sync report from testing Apps"""
# standard library
import os
import shutil
import sys
from functools import cached_property
from pathlib import Path

# third-party
import typer


class SyncTemplate:
    """."""

    def __init__(self):
        """Initialize instance properties"""

        # properties

        self.app_common_dst_path = Path('_app_common/')
        self.organization_basic_dst_path = Path('organization/basic/')
        self.organization_egress_dst_path = Path('organization/egress/')
        self.organization_ingress_dst_path = Path('organization/ingress/')
        self.playbook_action_dst_path = Path('playbook/actions/')
        self.playbook_basic_dst_path = Path('playbook/basic/')
        self.playbook_utility_dst_path = Path('playbook/utility/')
        self.api_service_basic_dst_path = Path('api_service/basic/')
        self.api_service_flask_dst_path = Path('api_service/flask/')
        self.trigger_service_basic_dst_path = Path('trigger_service/basic/')
        self.webhook_trigger_service_basic_dst_path = Path('webhook_trigger_service/basic/')

    def _copy_file(self, src_file, dst_file):
        """."""
        print('copying', src_file, dst_file)
        shutil.copy(src_file, dst_file)

    @cached_property
    def base_path(self) -> Path:
        """."""
        tc_template_dir = os.getenv('TC_TEMPLATE_DIR')
        if tc_template_dir is None:
            print('TC_TEMPLATE_DIR is not set.')
            sys.exit(1)

        tc_template_dir = Path(os.path.expanduser(tc_template_dir))
        if not tc_template_dir.is_dir():
            print(f'TC_TEMPLATE_DIR is not a directory: {tc_template_dir}')
            sys.exit(1)

        return tc_template_dir

    @cached_property
    def app_common_template_files(self) -> list[str]:
        """."""
        return [
            '.coveragerc',
            '.pre-commit-config.yaml',
            'gitignore',
            'pyproject.toml',
            'requirements.txt',
        ]

    def sync_playbook_actions(self):
        """."""
        src_path = self.base_path / 'tcpb-tcex-4-actions-template/'
        for file in src_path.rglob('*'):
            # only process items at the top level
            if file.parent != src_path:
                continue

            if file.is_dir():
                if file.name.startswith('.'):
                    continue

                if file.name in ['tests']:
                    shutil.rmtree(self.playbook_action_dst_path / file.name)
                    shutil.copytree(file, self.playbook_action_dst_path / file.name)
            elif file.is_file():
                filename = file.name
                if file.name == '.gitignore':
                    filename = 'gitignore'

                # send to most specific location first
                if file.name in [
                    'app_inputs.json',
                    'app_inputs.py',
                    'app.py',
                    'install.json',
                    'layout.json',
                    'README.md',
                ]:
                    self._copy_file(file, self.playbook_action_dst_path / filename)
                # send to parent location
                elif file.name in [
                    'playbook_app.py',
                    'run.py',
                    'run_local.py',
                ]:
                    self._copy_file(file, self.playbook_basic_dst_path / filename)
                # send to parent location
                elif file.name in self.app_common_template_files:
                    self._copy_file(file, self.app_common_dst_path / filename)

    def sync_organization_basic(self):
        """."""
        src_path = self.base_path / 'tc-tcex-4-basic-template/'
        for file in src_path.rglob('*'):
            # only process items at the top level
            if file.parent != src_path:
                continue

            if file.is_file():
                filename = file.name
                if file.name == '.gitignore':
                    filename = 'gitignore'

                # send to most specific location first
                if filename in [
                    'app_inputs.py',
                    'app.py',
                    'install.json',
                    'job_app.py',
                    'README.md',
                    'run_local.py',
                    'run.py',
                ]:
                    self._copy_file(file, self.organization_basic_dst_path / filename)
                # send to parent location
                elif filename in self.app_common_template_files:
                    self._copy_file(file, self.app_common_dst_path / filename)

    def sync_organization_egress(self, input_dir, output_dir):
        """."""
        for file in input_dir.rglob('*'):
            # only process items at the top level
            if file.parent != input_dir:
                continue

            if file.is_file():
                filename = file.name
                if file.name == '.gitignore':
                    filename = 'gitignore'

                # send to most specific location first
                if filename in [
                    'app_inputs.json',
                    'app_inputs.py',
                    'app.py',
                    'install.json',
                    'README.md',
                    'tcex.json',
                ]:
                    self._copy_file(file, output_dir / filename)
                # send to parent location
                elif file.name in [
                    'job_app.py',
                    'run.py',
                    'run_local.py',
                ]:
                    self._copy_file(file, self.organization_basic_dst_path / filename)

    def sync_playbook_basic(self):
        """."""
        src_path = self.base_path / 'tcpb-tcex-4-basic-template/'
        for file in src_path.rglob('*'):
            # only process items at the top level
            if file.parent != src_path:
                continue

            if file.is_file():
                filename = file.name
                if file.name == '.gitignore':
                    filename = 'gitignore'

                # send to most specific location first
                if filename in [
                    'app_inputs.py',
                    'app.py',
                    'install.json',
                    'playbook_app.py',
                    'README.md',
                    'run_local.py',
                    'run.py',
                ]:
                    self._copy_file(file, self.playbook_basic_dst_path / filename)
                # send to parent location
                elif filename in self.app_common_template_files:
                    self._copy_file(file, self.app_common_dst_path / filename)

    def sync_api_service_flask(self):
        """."""
        src_path = self.base_path / 'tcva-tcex-4-flask-template/'
        dst_path = self.api_service_flask_dst_path
        for file in src_path.rglob('*'):
            # only process items at the top level
            if file.parent != src_path:
                continue

            if file.is_dir():
                if file.name.startswith('.'):
                    continue

                if file.name in ['tests']:
                    shutil.rmtree(dst_path / file.name)
                    shutil.copytree(file, dst_path / file.name)
            elif file.is_file():
                filename = file.name
                if file.name == '.gitignore':
                    filename = 'gitignore'

                # send to most specific location first
                if file.name in [
                    'app_inputs.json',
                    'app_inputs.py',
                    'api_service_app.py',
                    'app.py',
                    'install.json',
                    'README.md',
                    'requirements.txt',
                    'run.py',
                ]:
                    self._copy_file(file, dst_path / filename)
                # send to parent location
                # elif file.name in self.app_common_template_files:
                #     self._copy_file(file, self.app_common_dst_path / filename)

    def sync_api_service_basic(self):
        """."""
        src_path = self.base_path / 'tcva-tcex-4-basic-template/'
        dst_path = self.api_service_basic_dst_path
        for file in src_path.rglob('*'):
            # only process items at the top level
            if file.parent != src_path:
                continue

            if file.is_dir():
                if file.name.startswith('.'):
                    continue

                if file.name in ['tests']:
                    shutil.rmtree(dst_path / file.name)
                    shutil.copytree(file, dst_path / file.name)
            elif file.is_file():
                filename = file.name
                if file.name == '.gitignore':
                    filename = 'gitignore'

                # send to most specific location first
                if file.name in [
                    'app_inputs.json',
                    'app_inputs.py',
                    'api_service_app.py',
                    'app.py',
                    'install.json',
                    'README.md',
                    'requirements.txt',
                    'run.py',
                ]:
                    self._copy_file(file, dst_path / filename)
                # send to parent location
                elif file.name in self.app_common_template_files:
                    self._copy_file(file, self.app_common_dst_path / filename)

    def sync_trigger_service_basic(self):
        """."""
        src_path = self.base_path / 'tcvc-tcex-4-basic-template/'
        dst_path = self.trigger_service_basic_dst_path
        for file in src_path.rglob('*'):
            # only process items at the top level
            if file.parent != src_path:
                continue

            if file.is_dir():
                if file.name.startswith('.'):
                    continue

                if file.name in ['tests']:
                    shutil.rmtree(dst_path / file.name)
                    shutil.copytree(file, dst_path / file.name)
            elif file.is_file():
                filename = file.name
                if file.name == '.gitignore':
                    filename = 'gitignore'

                # send to most specific location first
                if file.name in [
                    'app_inputs.json',
                    'app_inputs.py',
                    'service_app.py',
                    'app.py',
                    'install.json',
                    'README.md',
                    'requirements.txt',
                    'run.py',
                ]:
                    self._copy_file(file, dst_path / filename)
                # send to parent location
                elif file.name in self.app_common_template_files:
                    self._copy_file(file, self.app_common_dst_path / filename)

    def sync_webhook_trigger_service_basic(self):
        """."""
        src_path = self.base_path / 'tcvw-tcex-4-basic-template/'
        dst_path = self.webhook_trigger_service_basic_dst_path
        for file in src_path.rglob('*'):
            # only process items at the top level
            if file.parent != src_path:
                continue

            if file.is_dir():
                if file.name.startswith('.'):
                    continue

                if file.name in ['tests']:
                    shutil.rmtree(dst_path / file.name)
                    shutil.copytree(file, dst_path / file.name)
            elif file.is_file():
                filename = file.name
                if file.name == '.gitignore':
                    filename = 'gitignore'

                # send to most specific location first
                if file.name in [
                    'app_inputs.json',
                    'app_inputs.py',
                    'service_app.py',
                    'app.py',
                    'install.json',
                    'README.md',
                    'requirements.txt',
                    'run.py',
                ]:
                    self._copy_file(file, dst_path / filename)
                # send to parent location
                elif file.name in self.app_common_template_files:
                    self._copy_file(file, self.app_common_dst_path / filename)

    def sync_playbook_utility(self):
        """."""
        src_path = self.base_path / 'tcpb-tcex-4-utility-template/'
        for file in src_path.rglob('*'):
            # only process items at the top level
            if file.parent != src_path:
                continue

            if file.is_dir():
                if file.name.startswith('.'):
                    continue

                if file.name in ['tests']:
                    shutil.rmtree(self.playbook_utility_dst_path / file.name)
                    shutil.copytree(file, self.playbook_utility_dst_path / file.name)
            elif file.is_file():
                filename = file.name
                if file.name == '.gitignore':
                    filename = 'gitignore'

                # send to most specific location first
                if file.name in [
                    'app_inputs.json',
                    'app_inputs.py',
                    'app.py',
                    'install.json',
                    'README.md',
                ]:
                    self._copy_file(file, self.playbook_utility_dst_path / filename)
                # send to parent location
                elif file.name in [
                    'playbook_app.py',
                    'run.py',
                    'run_local.py',
                ]:
                    self._copy_file(file, self.playbook_basic_dst_path / filename)
                # send to parent location
                elif file.name in self.app_common_template_files:
                    self._copy_file(file, self.app_common_dst_path / filename)


#
# CLI
#

app = typer.Typer()
sync_template = SyncTemplate()


@app.command()
def sync(
    template_type: str = typer.Option(
        ..., '--type', help='The App type being initialized.', prompt=True
    ),
    template_name: str = typer.Option(
        ..., '--template', help='The App template to be used.', prompt=True
    ),
):
    """Sync template files"""
    match template_type:
        case 'api_service':
            match template_name:
                case 'basic':
                    sync_template.sync_api_service_basic()
                case 'flask':
                    sync_template.sync_api_service_flask()
                case _:
                    typer.secho(f'Invalid template name: {template_name}')
        case 'organization':
            match template_name:
                case 'basic':
                    sync_template.sync_organization_basic()
                case 'egress':
                    sync_template.sync_organization_egress(
                        input_dir=sync_template.base_path / 'tc-tcex-4-egress-template/',
                        output_dir=sync_template.organization_egress_dst_path,
                    )
                case 'ingress':
                    sync_template.sync_organization_egress(
                        input_dir=sync_template.base_path / 'tc-tcex-4-ingress-template/',
                        output_dir=sync_template.organization_ingress_dst_path,
                    )
        case 'playbook':
            match template_name:
                case 'actions':
                    sync_template.sync_playbook_actions()

                case 'basic':
                    sync_template.sync_playbook_basic()

                case 'utility':
                    sync_template.sync_playbook_utility()

                case _:
                    typer.secho(f'Invalid template name: {template_name}')
        case 'trigger_service':
            match template_name:
                case 'basic':
                    sync_template.sync_trigger_service_basic()
                case _:
                    typer.secho(f'Invalid template name: {template_name}')
        case 'webhook_trigger_service':
            match template_name:
                case 'basic':
                    sync_template.sync_webhook_trigger_service_basic()
                case _:
                    typer.secho(f'Invalid template name: {template_name}')

        case _:
            typer.secho(f'Invalid template type: {template_type}')


if __name__ == '__main__':
    app()
