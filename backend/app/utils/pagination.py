from typing import Tuple
from fastapi import Query

from fastapi_pagination import Params


async def get_pagination_params(
        page: int = Query(1, ge=1, description="Page number"),
        size: int = Query(10, ge=1, le=100, description="Items per page"),
) -> Params:
    """
    Get pagination parameters.

    Args:
        page: Page number (1-indexed)
        size: Items per page

    Returns:
        Pagination parameters
    """
    return Params(page=page, size=size)