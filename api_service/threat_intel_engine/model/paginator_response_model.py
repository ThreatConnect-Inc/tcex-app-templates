"""Model Definition"""
# standard library
from typing import List, Optional

# third-party
from pydantic import BaseModel


class PaginatorResponseModel(BaseModel):
    """Model Definition"""

    count: Optional[int]
    data: Optional[List[dict]]
    next: Optional[str]
    previous: Optional[str]
    total_count: Optional[int]
