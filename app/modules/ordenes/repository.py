from typing import Optional, Sequence
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.repository import BaseRepository
from app.modules.clientes.models import Vehiculo
from app.modules.ordenes.models import (
    EstadoOrden,
    HistorialEstadoOrden,
    ItemOrden,
    OrdenTrabajo,
)


class EstadoOrdenRepository:
    """
    Repositorio de sólo lectura para el catálogo estado_orden.
    NO hereda de BaseRepository para no exponer add, update ni delete (RN-19).
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_codigo(self, codigo: str) -> EstadoOrden | None:
        return await self.session.get(EstadoOrden, codigo)

    async def get_all_ordered(self) -> Sequence[EstadoOrden]:
        stmt = select(EstadoOrden).order_by(EstadoOrden.posicion)
        return (await self.session.execute(stmt)).scalars().all()

    async def count(self) -> int:
        stmt = select(func.count()).select_from(EstadoOrden)
        return (await self.session.execute(stmt)).scalar_one()


class OrdenTrabajoRepository(BaseRepository[OrdenTrabajo]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, OrdenTrabajo)

    async def get_detalle_by_id(self, orden_id: int) -> OrdenTrabajo | None:
        """
        Obtiene el detalle completo de una orden con precarga anticipada (selectinload)
        para evitar problemas de N+1 (Ejercicio 8).
        La cantidad de consultas es constante independientemente de los ítems.
        """
        stmt = (
            select(OrdenTrabajo)
            .where(OrdenTrabajo.id == orden_id)
            .options(
                selectinload(OrdenTrabajo.vehiculo).selectinload(Vehiculo.cliente),
                selectinload(OrdenTrabajo.items).selectinload(ItemOrden.repuesto),
                selectinload(OrdenTrabajo.historial),
            )
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def get_paginated(
        self, estado: Optional[str], skip: int, limit: int
    ) -> tuple[Sequence[OrdenTrabajo], int]:
        conditions = []
        if estado is not None:
            conditions.append(OrdenTrabajo.estado == estado)

        total_stmt = select(func.count()).select_from(OrdenTrabajo).where(*conditions)
        total = (await self.session.execute(total_stmt)).scalar_one()

        stmt = (
            select(OrdenTrabajo)
            .where(*conditions)
            .options(
                selectinload(OrdenTrabajo.vehiculo).selectinload(Vehiculo.cliente),
            )
            .order_by(OrdenTrabajo.id.desc())
            .offset(skip)
            .limit(limit)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return items, total

    async def get_by_cliente_id_paginated(
        self, cliente_id: int, skip: int, limit: int
    ) -> tuple[Sequence[OrdenTrabajo], int]:
        stmt_total = (
            select(func.count())
            .select_from(OrdenTrabajo)
            .join(Vehiculo, Vehiculo.id == OrdenTrabajo.vehiculo_id)
            .where(Vehiculo.cliente_id == cliente_id)
        )
        total = (await self.session.execute(stmt_total)).scalar_one()

        stmt = (
            select(OrdenTrabajo)
            .join(Vehiculo, Vehiculo.id == OrdenTrabajo.vehiculo_id)
            .where(Vehiculo.cliente_id == cliente_id)
            .options(
                selectinload(OrdenTrabajo.vehiculo).selectinload(Vehiculo.cliente),
            )
            .order_by(OrdenTrabajo.id.desc())
            .offset(skip)
            .limit(limit)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return items, total


class ItemOrdenRepository(BaseRepository[ItemOrden]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, ItemOrden)


class HistorialEstadoOrdenRepository(BaseRepository[HistorialEstadoOrden]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, HistorialEstadoOrden)
