from datetime import datetime, timedelta, timezone
from typing import Sequence
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.repository import BaseRepository
from app.modules.usuarios.models import (
    AsignacionRol,
    EventoSeguridad,
    IntentoAcceso,
    Usuario,
)


class UsuarioRepository(BaseRepository[Usuario]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Usuario)

    async def get_by_email(self, email: str) -> Usuario | None:
        stmt = select(Usuario).where(Usuario.email == email)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def count_active_admins(self) -> int:
        now = datetime.now(timezone.utc)
        stmt = (
            select(func.count(func.distinct(Usuario.id)))
            .join(AsignacionRol, AsignacionRol.usuario_id == Usuario.id)
            .where(
                Usuario.activo.is_(True),
                AsignacionRol.rol == "ADMIN",
                AsignacionRol.revocada_en.is_(None),
                (AsignacionRol.vence_en.is_(None) | (AsignacionRol.vence_en > now)),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()


class AsignacionRolRepository(BaseRepository[AsignacionRol]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, AsignacionRol)

    async def get_roles_vigentes_by_usuario_id(self, usuario_id: int) -> list[AsignacionRol]:
        now = datetime.now(timezone.utc)
        stmt = select(AsignacionRol).where(
            AsignacionRol.usuario_id == usuario_id,
            AsignacionRol.revocada_en.is_(None),
            (AsignacionRol.vence_en.is_(None) | (AsignacionRol.vence_en > now)),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_asignacion_abierta(self, usuario_id: int, rol: str) -> AsignacionRol | None:
        stmt = select(AsignacionRol).where(
            AsignacionRol.usuario_id == usuario_id,
            AsignacionRol.rol == rol,
            AsignacionRol.revocada_en.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all_by_usuario_id(self, usuario_id: int) -> list[AsignacionRol]:
        stmt = select(AsignacionRol).where(AsignacionRol.usuario_id == usuario_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class IntentoAccesoRepository(BaseRepository[IntentoAcceso]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, IntentoAcceso)

    async def count_recent_failures(
        self, email: str, ip: str, window_seconds: int = 60
    ) -> int:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=window_seconds)

        # Buscar el último intento exitoso para reiniciar el contador si lo hubo
        stmt_last_success = (
            select(func.max(IntentoAcceso.cuando))
            .where(
                IntentoAcceso.email == email,
                IntentoAcceso.ip == ip,
                IntentoAcceso.exito.is_(True),
            )
        )
        last_success = (await self.session.execute(stmt_last_success)).scalar_one_or_none()

        conditions = [
            IntentoAcceso.email == email,
            IntentoAcceso.ip == ip,
            IntentoAcceso.exito.is_(False),
            IntentoAcceso.cuando >= cutoff,
        ]
        if last_success is not None:
            conditions.append(IntentoAcceso.cuando > last_success)

        stmt = select(func.count()).select_from(IntentoAcceso).where(*conditions)
        return (await self.session.execute(stmt)).scalar_one()


class EventoSeguridadRepository(BaseRepository[EventoSeguridad]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, EventoSeguridad)

    async def get_paginated(self, skip: int, limit: int) -> tuple[Sequence[EventoSeguridad], int]:
        total_stmt = select(func.count()).select_from(EventoSeguridad)
        total = (await self.session.execute(total_stmt)).scalar_one()

        stmt = (
            select(EventoSeguridad)
            .order_by(EventoSeguridad.cuando.desc())
            .offset(skip)
            .limit(limit)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return items, total
