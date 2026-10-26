from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Sequence
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.repository import BaseRepository, SoftDeleteRepository
from app.modules.repuestos.models import (
    HistorialPrecio,
    MovimientoStock,
    Repuesto,
)


class RepuestoRepository(SoftDeleteRepository[Repuesto]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Repuesto)

    async def get_by_codigo_activo(self, codigo: str) -> Repuesto | None:
        stmt = select(Repuesto).where(
            Repuesto.codigo == codigo,
            Repuesto.borrado_en.is_(None),
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def search_paginated(
        self, q: Optional[str], skip: int, limit: int
    ) -> tuple[Sequence[Repuesto], int]:
        conditions = [Repuesto.borrado_en.is_(None)]
        if q is not None and q.strip() != "":
            conditions.append(Repuesto.descripcion.ilike(f"%{q}%"))

        total_stmt = select(func.count()).select_from(Repuesto).where(*conditions)
        total = (await self.session.execute(total_stmt)).scalar_one()

        stmt = (
            select(Repuesto)
            .where(*conditions)
            .order_by(Repuesto.id)
            .offset(skip)
            .limit(limit)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return items, total

    async def modify_stock(
        self,
        repuesto_id: int,
        delta: int,
        usuario_id: int,
        motivo: str,
        orden_id: Optional[int] = None,
    ) -> tuple[Repuesto, MovimientoStock]:
        """
        Punto único de escritura de stock (RN-14).
        Actualiza el stock del repuesto y crea el MovimientoStock correspondiente.
        """
        repuesto = await self.get_by_id(repuesto_id)
        if not repuesto:
            raise ValueError(f"Repuesto con id {repuesto_id} no encontrado")

        new_stock = repuesto.stock + delta
        if new_stock < 0:
            raise ValueError(
                f"Stock insuficiente para el repuesto '{repuesto.descripcion}'. Stock actual: {repuesto.stock}, requerido: {-delta}"
            )

        repuesto.stock = new_stock
        movimiento = MovimientoStock(
            repuesto_id=repuesto.id,
            orden_id=orden_id,
            usuario_id=usuario_id,
            cantidad=delta,
            motivo=motivo,
            cuando=datetime.now(timezone.utc),
        )
        self.session.add(movimiento)
        await self.session.flush()
        return repuesto, movimiento

    async def record_price_change(
        self,
        repuesto_id: int,
        usuario_id: int,
        precio_anterior: Decimal,
        precio_nuevo: Decimal,
    ) -> HistorialPrecio:
        """Registra un cambio de precio en historial_precio_repuesto (RN-20)."""
        historial = HistorialPrecio(
            repuesto_id=repuesto_id,
            usuario_id=usuario_id,
            precio_anterior=precio_anterior,
            precio_nuevo=precio_nuevo,
            cuando=datetime.now(timezone.utc),
        )
        self.session.add(historial)
        await self.session.flush()
        return historial


class MovimientoStockRepository(BaseRepository[MovimientoStock]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, MovimientoStock)

    async def get_by_repuesto_id(self, repuesto_id: int) -> Sequence[MovimientoStock]:
        stmt = (
            select(MovimientoStock)
            .where(MovimientoStock.repuesto_id == repuesto_id)
            .order_by(MovimientoStock.cuando.desc())
        )
        return (await self.session.execute(stmt)).scalars().all()


class HistorialPrecioRepository(BaseRepository[HistorialPrecio]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, HistorialPrecio)

    async def get_by_repuesto_id(self, repuesto_id: int) -> Sequence[HistorialPrecio]:
        stmt = (
            select(HistorialPrecio)
            .where(HistorialPrecio.repuesto_id == repuesto_id)
            .order_by(HistorialPrecio.cuando.desc())
        )
        return (await self.session.execute(stmt)).scalars().all()
