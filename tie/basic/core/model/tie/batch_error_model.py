"""Model Definition"""

from datetime import UTC, datetime
from typing import ClassVar

from pydantic import Field

from core.json_db import Index
from core.model.model_base import ModelBase
from core.model.response.paginated_response import PaginatedResponseModel

error_codes_name_map = {
    '0x1001': 'General Error',
    '0x1002': 'Permission Error',
    '0x1003': 'JsonSyntax Error',
    '0x1004': 'Internal Error',
    '0x1005': 'Invalid Indicator Error',
    '0x1006': 'Invalid Group Error',
    '0x1007': 'Item Not Found Error',
    '0x1008': 'Indicator Limit Error',
    '0x1009': 'Association Error',
    '0x100A': 'Duplicate Item Error',
    '0x100B': 'File IO Error',
    '0x2001': 'Indicator Partial Loss Error',
    '0x2002': 'Group Partial Loss Error',
    '0x2003': 'File Hash Merge Error',
    '0x3001': 'File Hash Merge Error',
    'unknown': 'Unknown Error',
}


class BatchErrorModel(ModelBase):
    """Model Definition"""

    id: str = Index()
    code: str = Field(..., description='')
    date_added: datetime = Field(default_factory=lambda: datetime.now(UTC), description='')
    message: str = Field(..., description='')
    reason: str = Field(..., description='')
    request_id: str = Field(..., description='')

    class Config:
        """Model Config"""

        json_encoders: ClassVar[dict] = {
            datetime: lambda v: v.strftime('%Y-%m-%d %H:%M:%S'),
        }


class UnknownBatchErrorModel(BatchErrorModel):
    """Model Definition"""


class GeneralErrorBatchErrorModel(BatchErrorModel):
    """Model Definition"""


class PermissionBatchErrorModel(BatchErrorModel):
    """Model Definition"""


class JsonSyntaxBatchErrorModel(BatchErrorModel):
    """Model Definition"""


class InternalBatchErrorModel(BatchErrorModel):
    """Model Definition"""


class InvalidIndicatorBatchErrorModel(BatchErrorModel):
    """Model Definition"""


class InvalidGroupBatchErrorModel(BatchErrorModel):
    """Model Definition"""


class ItemNotFoundBatchErrorModel(BatchErrorModel):
    """Model Definition"""


class IndicatorLimitBatchErrorModel(BatchErrorModel):
    """Model Definition"""


class AssociationErrorBatchErrorModel(BatchErrorModel):
    """Model Definition"""


class DuplicateItemBatchErrorModel(BatchErrorModel):
    """Model Definition"""


class FileIOBatchErrorModel(BatchErrorModel):
    """Model Definition"""


class IndicatorPartialLossBatchErrorModel(BatchErrorModel):
    """Model Definition"""


class GroupPartialLossBatchErrorModel(BatchErrorModel):
    """Model Definition"""


class FileHashMergeBatchErrorModel(BatchErrorModel):
    """Model Definition"""


error_codes_model_map: dict[str, type[BatchErrorModel]] = {
    '0x1001': GeneralErrorBatchErrorModel,
    '0x1002': PermissionBatchErrorModel,
    '0x1003': JsonSyntaxBatchErrorModel,
    '0x1004': InternalBatchErrorModel,
    '0x1005': InvalidIndicatorBatchErrorModel,
    '0x1006': InvalidGroupBatchErrorModel,
    '0x1007': ItemNotFoundBatchErrorModel,
    '0x1008': IndicatorLimitBatchErrorModel,
    '0x1009': AssociationErrorBatchErrorModel,
    '0x100A': DuplicateItemBatchErrorModel,
    '0x100B': FileIOBatchErrorModel,
    '0x2001': IndicatorPartialLossBatchErrorModel,
    '0x2002': GroupPartialLossBatchErrorModel,
    '0x2003': FileHashMergeBatchErrorModel,
    '0x3001': FileHashMergeBatchErrorModel,
    'unknown': UnknownBatchErrorModel,
}


class BatchErrorPaginatedResponseModel(PaginatedResponseModel[BatchErrorModel]):
    """Model Definition"""


class JobBatchErrorIndexModel(ModelBase):
    """Model Definition"""

    request_id: str = Index()
    error_ids: list[str] = Field(default_factory=list)
