"""Model Definition"""
# third-party
import arrow
from pydantic import BaseModel, Field


class BatchErrorModel(BaseModel):
    """Model Definition"""

    id: int = Field(..., description='')
    code: str = Field(..., description='')
    date_added: arrow.Arrow = Field(..., description='')
    message: str = Field(..., description='')
    reason: str = Field(..., description='')
    request_id: str = Field(..., description='')

    class Config:
        """Model Config"""

        arbitrary_types_allowed = True
        json_encoders = {arrow.Arrow: lambda v: v.isoformat()}
        orm_mode = True
