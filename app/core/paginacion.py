import math
from typing import Generic, Sequence, TypeVar
from fastapi import HTTPException, status
from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int


def paginate(items: Sequence[T], total: int, page: int, size: int) -> PaginatedResponse[T]:
    """
    Builds the paginated response envelope {items, total, page, size, pages}.
    If total is 0, pages is 1. If page > pages, raises 422.
    """
    if total == 0:
        pages = 1
    else:
        pages = math.ceil(total / size)

    if page > pages:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"La página {page} no existe: hay {pages}",
        )

    return PaginatedResponse(
        items=list(items),
        total=total,
        page=page,
        size=size,
        pages=pages,
    )
