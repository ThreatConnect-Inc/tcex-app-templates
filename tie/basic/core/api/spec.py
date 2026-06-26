"""SpecTree OpenAPI Specification"""

import os

from offapi import OpenAPITemplate
from spectree import SpecTree, Tag
from tcex.app.config.install_json import InstallJson

from core.model.model_base import ModelBase

ij = InstallJson()


class DescriptionItemModel(ModelBase):
    """Description Item Model"""

    field: list[str]
    msg: str
    type: str


class ValidationErrorModel(ModelBase):
    """Validation Error Model"""

    code: str
    description: list[DescriptionItemModel]
    title: str


# determine servers base on if in "production" or "development" mode
if os.getenv('TCEX_RUN_LOCAL', '0') == '1':
    servers = [
        {
            'url': '/',
            'description': 'Local Development Server',
        },
    ]
else:
    servers = [
        {
            'url': '/api/services/{userPath}/v1/',
            'description': 'Production Server',
            'variables': {
                'userPath': {
                    'default': ij.model.display_path or '',
                    'description': 'The default user defined path.',
                }
            },
        },
    ]

spec = SpecTree(
    'falcon',
    # annotations=True,  # can't be used with skip_validation
    contact={
        'name': 'ThreatConnect',
        'url': 'https://threatconnect.com',
    },
    description=f'ThreatConnect Service App OpenAPI Specifications for {ij.model.display_name}.',
    license={
        'name': 'Apache-2.0',
        'url': 'https://www.apache.org/licenses/LICENSE-2.0',
    },
    page_templates={
        # 'redoc': OpenAPITemplate.REDOC.value,
        'swagger': OpenAPITemplate.SWAGGER.value,
        # 'scalar': OpenAPITemplate.SCALAR.value,
    },
    # path='apidoc',
    servers=servers,
    title=f'{ij.model.display_name} - OpenAPI Spec',
    validation_error_model=ValidationErrorModel,
    validation_error_status=400,
    version=str(ij.model.program_version),
    # config
    annotations=False,
)

tag_download = Tag(
    name='[Internal] Download',
    description='Endpoints related to the Download feature',
)

tag_job = Tag(
    name='[Internal] Job',
    description='Endpoints related to Job viewing and updating',
)

tag_metric = Tag(
    name='[Internal] Metric',
    description='Endpoints related to metrics',
)

tag_settings = Tag(
    name='[Internal] Setting',
    description='Endpoints related to settings',
)

tag_task = Tag(
    name='[Internal] Task',
    description='Endpoints related to tasks',
)

tag_util = Tag(
    name='[Internal] Util',
    description='Endpoints related to utility functions',
)

tag_service = Tag(
    name='[Internal] Service Provider',
    description='Endpoints related to the service provider',
)

tag_notification = Tag(
    name='[Internal] Notification',
    description='Endpoints related to pipeline health notifications',
)
