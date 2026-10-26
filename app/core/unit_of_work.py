from abc import ABC
from types import TracebackType
from typing import Type
from sqlalchemy.ext.asyncio import AsyncSession


class UnitOfWork(ABC):
    """
    Base asynchronous Unit of Work context manager.
    Commits on exit if no exception was raised, rollbacks on error,
    and does NOT close the session because it did not create it.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
