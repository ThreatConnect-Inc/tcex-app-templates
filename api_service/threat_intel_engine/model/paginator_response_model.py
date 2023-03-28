"""Model Definition"""

# third-party
from pydantic import BaseModel


class PaginatorResponseModel(BaseModel):
    """Model Definition"""

    count: int | None
    data: list[dict] | None
    next: str | None
    previous: str | None
    total_count: int | None
