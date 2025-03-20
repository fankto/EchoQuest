from typing import Any, Callable, TypeVar, Awaitable, Type, Optional
from contextlib import asynccontextmanager
import inspect

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.exceptions import DatabaseError

T = TypeVar('T')


@asynccontextmanager
async def transaction(db: AsyncSession):
    """
    Context manager for database transactions

    Usage:
        async with transaction(db):
            # database operations

    Raises:
        DatabaseError: If there's an error during the transaction
    """
    try:
        yield
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Transaction error: {str(e)}")
        raise DatabaseError(f"Database operation failed: {str(e)}")


async def transactional(
        func: Callable[..., Awaitable[T]]
) -> Callable[..., Awaitable[T]]:
    """
    Decorator for methods that need transaction management

    Usage:
        @transactional
        async def my_function(db: AsyncSession, arg1, arg2):
            # database operations

    Raises:
        DatabaseError: If there's an error during the transaction
    """

    async def wrapper(*args, **kwargs):
        # Extract db session from args or kwargs
        sig = inspect.signature(func)
        params = sig.parameters

        db = None
        for i, (name, param) in enumerate(params.items()):
            if param.annotation == AsyncSession:
                if i < len(args):
                    db = args[i]
                else:
                    db = kwargs.get(name)

        if db is None:
            raise ValueError("No AsyncSession parameter found in function signature")

        async with transaction(db):
            return await func(*args, **kwargs)

    return wrapper


class Transactional:
    """
    Class decorator for adding transaction management to all async methods

    Usage:
        @Transactional
        class MyService:
            async def my_method(self, db: AsyncSession, arg1, arg2):
                # database operations
    """

    def __init__(self, cls: Type):
        self.cls = cls
        for name, method in inspect.getmembers(cls, inspect.iscoroutinefunction):
            setattr(cls, name, transactional(method))

    def __call__(self, *args, **kwargs):
        return self.cls(*args, **kwargs)