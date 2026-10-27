from typing import Optional, Sequence
from fastapi import HTTPException, status
from app.core.paginacion import PaginatedResponse, paginate
from app.modules.repuestos.models import (
    HistorialPrecio,
    MovimientoStock,
    Repuesto,
)
from app.modules.repuestos.schemas import (
    ActualizarRepuestoRequest,
    CrearRepuestoRequest,
    HistorialPrecioResponse,
    MovimientoStockResponse,
    ReponerRepuestoRequest,
    RepuestoResponse,
)
from app.modules.repuestos.unit_of_work import RepuestosUnitOfWork
from app.modules.usuarios.models import Usuario


class RepuestosService:
    def __init__(self, uow: RepuestosUnitOfWork):
        self.uow = uow

    async def listar_repuestos(
        self, q: Optional[str], page: int, size: int
    ) -> PaginatedResponse[RepuestoResponse]:
        async with self.uow:
            skip = (page - 1) * size
            items, total = await self.uow.repuestos.search_paginated(q, skip, size)
            responses = [RepuestoResponse.model_validate(r) for r in items]
            return paginate(responses, total=total, page=page, size=size)

    async def get_repuesto(self, repuesto_id: int) -> RepuestoResponse:
        async with self.uow:
            repuesto = await self.uow.repuestos.get_by_id(repuesto_id)
            if not repuesto:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Repuesto no encontrado",
                )
            return RepuestoResponse.model_validate(repuesto)

    async def crear_repuesto(
        self, data: CrearRepuestoRequest, admin: Usuario
    ) -> RepuestoResponse:
        async with self.uow:
            # Unicidad de código garantizada exclusivamente por la base de datos (página 20)
            repuesto = Repuesto(
                codigo=data.codigo,
                descripcion=data.descripcion,
                precio=data.precio,
                stock=0,
                borrado_en=None,
            )
            await self.uow.repuestos.add(repuesto)

            if data.stock_inicial > 0:
                # Punto único de escritura de stock (RN-14)
                await self.uow.repuestos.modify_stock(
                    repuesto_id=repuesto.id,
                    delta=data.stock_inicial,
                    usuario_id=admin.id,
                    motivo="Stock inicial",
                )

            return RepuestoResponse.model_validate(repuesto)

    async def actualizar_repuesto(
        self, repuesto_id: int, data: ActualizarRepuestoRequest, admin: Usuario
    ) -> RepuestoResponse:
        data_dict = data.model_dump(exclude_unset=True)
        if not data_dict:
            # Si no envió campos, devuelve el repuesto sin cambios
            return await self.get_repuesto(repuesto_id)

        async with self.uow:
            repuesto = await self.uow.repuestos.get_by_id(repuesto_id)
            if not repuesto:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Repuesto no encontrado",
                )

            if "descripcion" in data_dict:
                repuesto.descripcion = data_dict["descripcion"]

            if "precio" in data_dict:
                nuevo_precio = data_dict["precio"]
                if nuevo_precio != repuesto.precio:
                    # RN-20: registrar cambio de precio en la misma transacción
                    precio_ant = repuesto.precio
                    repuesto.precio = nuevo_precio
                    await self.uow.repuestos.record_price_change(
                        repuesto_id=repuesto.id,
                        usuario_id=admin.id,
                        precio_anterior=precio_ant,
                        precio_nuevo=nuevo_precio,
                    )

            await self.uow.repuestos.update(repuesto)
            return RepuestoResponse.model_validate(repuesto)

    async def dar_de_baja_repuesto(self, repuesto_id: int) -> None:
        async with self.uow:
            repuesto = await self.uow.repuestos.get_by_id(repuesto_id)
            if not repuesto:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Repuesto no encontrado",
                )
            await self.uow.repuestos.soft_delete(repuesto)

    async def reponer_stock(
        self, repuesto_id: int, data: ReponerRepuestoRequest, admin: Usuario
    ) -> RepuestoResponse:
        async with self.uow:
            repuesto = await self.uow.repuestos.get_by_id(repuesto_id)
            if not repuesto:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Repuesto no encontrado",
                )

            # Punto único de escritura de stock (RN-14)
            repuesto_mod, _ = await self.uow.repuestos.modify_stock(
                repuesto_id=repuesto_id,
                delta=data.cantidad,
                usuario_id=admin.id,
                motivo=data.motivo,
            )
            return RepuestoResponse.model_validate(repuesto_mod)

    async def get_movimientos(
        self, repuesto_id: int
    ) -> Sequence[MovimientoStock]:
        async with self.uow:
            repuesto = await self.uow.repuestos.get_by_id(repuesto_id)
            if not repuesto:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Repuesto no encontrado",
                )
            return await self.uow.movimientos.get_by_repuesto_id(repuesto_id)

    async def get_historial_precios(
        self, repuesto_id: int
    ) -> Sequence[HistorialPrecio]:
        async with self.uow:
            repuesto = await self.uow.repuestos.get_by_id(repuesto_id)
            if not repuesto:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Repuesto no encontrado",
                )
            return await self.uow.historial_precios.get_by_repuesto_id(repuesto_id)
