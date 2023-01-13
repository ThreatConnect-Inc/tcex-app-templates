"""Model Definition"""
# third-party
from pydantic import BaseModel, Extra, Field


class MultipartFormDataModel(BaseModel):
    """Model Definition"""

    content: bytes = Field(..., description='The content of the file.')
    content_type: str = Field(..., description='The Content-Type for the file.')
    filename: str = Field(..., description='The filename for the file.')
    name: str = Field(..., description='The name for the part.')

    class Config:
        """Model Config"""

        arbitrary_types_allowed = True
        extra = Extra.forbid
