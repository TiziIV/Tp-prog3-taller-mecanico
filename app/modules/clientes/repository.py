from typing import Sequence
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.repository import BaseRepository, SoftDeleteRepository
from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.ordenes.models import EstadoOrden, OrdenTrabajo


class ClienteRepository(BaseRepository[Cliente]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Cliente)

    async def get_by_documento(self, documento: str) -> Cliente | None:
        stmt = select(Cliente).where(Cliente.documento == documento)
        return (await self.session.execute(stmt)).scalars().first()

    async def get_by_usuario_id(self, usuario_id: int) -> Cliente | None:
        stmt = select(Cliente).where(Cliente.usuario_id == usuario_id)
        return (await self.session.execute(stmt)).scalars().first()

    async def get_by_id_with_vehiculos(self, id: int) -> Cliente | None:
        stmt = (
            select(Cliente)
            .where(Cliente.id == id)
            .options(selectinload(Cliente.vehiculos))
        )
        cliente = (await self.session.execute(stmt)).scalars().first()
        if cliente:
            # Filtrar en memoria sólo los vehículos vigentes (sin borrado lógico)
            cliente.vehiculos = [v for v in cliente.vehiculos if v.borrado_en is None]
        return cliente


class VehiculoRepository(SoftDeleteRepository[Vehiculo]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Vehiculo)

    async def get_by_patente_activa(self, patente: str) -> Vehiculo | None:
        stmt = select(Vehiculo).where(
            Vehiculo.patente == patente,
            Vehiculo.borrado_en.is_(None),
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def get_by_cliente_id(self, cliente_id: int) -> Sequence[Vehiculo]:
        stmt = select(Vehiculo).where(
            Vehiculo.cliente_id == cliente_id,
            Vehiculo.borrado_en.is_(None),
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def count_open_orders(self, vehiculo_id: int) -> int:
        """Counts orders of this vehicle whose status is NOT marked as final (es_final = False)."""
        stmt = (
            select(func.count())
            .select_from(OrdenTrabajo)
            .join(EstadoOrden, EstadoOrden.codigo == OrdenTrabajo.estado)
            .where(
                OrdenTrabajo.vehiculo_id == vehiculo_id,
                EstadoOrden.es_final.is_(False),
            )
        )
        return (await self.session.execute(stmt)).scalar_one()
