from datetime import datetime, timezone
from typing import Any, Generic, Sequence, Type, TypeVar
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseRepository(Generic[T]):
    def __init__(self, session: AsyncSession, model_cls: Type[T]):
        self.session = session
        self.model_cls = model_cls

    async def get_by_id(self, id: Any) -> T | None:
        return await self.session.get(self.model_cls, id)

    async def get_all(self, skip: int = 0, limit: int = 100) -> Sequence[T]:
        stmt = select(self.model_cls).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model_cls)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def add(self, entity: T) -> T:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def update(self, entity: T) -> T:
        await self.session.flush()
        return entity

    async def delete(self, entity: T) -> None:
        await self.session.delete(entity)
        await self.session.flush()


class SoftDeleteRepository(BaseRepository[T]):
    async def get_by_id(self, id: Any) -> T | None:
        stmt = select(self.model_cls).where(
            getattr(self.model_cls, "id") == id,
            getattr(self.model_cls, "borrado_en").is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_id_including_deleted(self, id: Any) -> T | None:
        return await super().get_by_id(id)

    async def get_all(self, skip: int = 0, limit: int = 100) -> Sequence[T]:
        stmt = (
            select(self.model_cls)
            .where(getattr(self.model_cls, "borrado_en").is_(None))
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count(self) -> int:
        stmt = (
            select(func.count())
            .select_from(self.model_cls)
            .where(getattr(self.model_cls, "borrado_en").is_(None))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def soft_delete(self, entity: T) -> T:
        setattr(entity, "borrado_en", datetime.now(timezone.utc))
        await self.session.flush()
        return entity
