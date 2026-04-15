"""Model Definition"""

import logging

from pydantic import BaseModel, ConfigDict

from core.api.validation.models.query_param_model import value_to_camel

# logger
logger = logging.getLogger('tcex')


class ModelBase(BaseModel):
    """Model Definition"""

    model_config = ConfigDict(
        alias_generator=value_to_camel,
        extra='forbid',
        validate_default=True,
        validate_assignment=True,
    )
