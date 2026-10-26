import asyncio
from datetime import datetime, timezone
import logging
from typing import Optional
from fastapi import BackgroundTasks, HTTPException, status
from app.core.paginacion import PaginatedResponse, paginate
from app.modules.ordenes.models import (
    EstadoOrden,
    HistorialEstadoOrden,
    ItemOrden,
    OrdenTrabajo,
)
from app.modules.ordenes.schemas import (
    CrearOrdenRequest,
    EstadoOrdenResponse,
    HistorialEstadoOrdenDetalleResponse,
    ItemOrdenDetalleResponse,
    OrdenDetalleResponse,
    OrdenListItemResponse,
)
from app.modules.ordenes.unit_of_work import OrdenesUnitOfWork
from app.modules.usuarios.models import Usuario

logger = logging.getLogger("taller_mecanico")


async def notificar_cliente_orden_terminada(orden_id: int, cliente_nombre: str) -> None:
    """
    Tarea en segundo plano (BackgroundTasks) para notificar al cliente (Ejercicio 8, sección 3.9).
    Simulado con asyncio.sleep(0.5) y un registro en el log.
    """
    await asyncio.sleep(0.5)
    logger.info(
        f"[AVISO CLIENTE] Estimado/a {cliente_nombre}, su orden de trabajo #{orden_id} ha sido TERMINADA y está lista para retirar."
    )


class OrdenesService:
    def __init__(self, uow: OrdenesUnitOfWork):
        self.uow = uow

    def _to_orden_detalle_response(self, orden: OrdenTrabajo) -> OrdenDetalleResponse:
        patente = orden.vehiculo.patente if orden.vehiculo else ""
        cliente_nombre = (
            orden.vehiculo.cliente.nombre
            if orden.vehiculo and orden.vehiculo.cliente
            else ""
        )

        items_res = []
        for it in orden.items:
            subtotal = it.cantidad * it.precio_unitario
            items_res.append(
                ItemOrdenDetalleResponse(
                    repuesto_id=it.repuesto_id,
                    codigo=it.repuesto.codigo if it.repuesto else "",
                    descripcion=it.repuesto.descripcion if it.repuesto else "",
                    cantidad=it.cantidad,
                    precio_unitario=it.precio_unitario,
                    subtotal=subtotal,
                )
            )

        historial_res = [
            HistorialEstadoOrdenDetalleResponse(
                desde_estado=h.desde_estado,
                hasta_estado=h.hasta_estado,
                usuario_id=h.usuario_id,
                cuando=h.cuando,
            )
            for h in orden.historial
        ]

        return OrdenDetalleResponse(
            id=orden.id,
            estado=orden.estado,
            patente=patente,
            total=orden.total,
            creada_en=orden.creada_en,
            mecanico_id=orden.mecanico_id,
            falla=orden.falla,
            cliente=cliente_nombre,
            items=items_res,
            historial=historial_res,
        )

    def _to_orden_list_item(self, orden: OrdenTrabajo) -> OrdenListItemResponse:
        patente = orden.vehiculo.patente if orden.vehiculo else ""
        cliente_nombre = (
            orden.vehiculo.cliente.nombre
            if orden.vehiculo and orden.vehiculo.cliente
            else ""
        )
        return OrdenListItemResponse(
            id=orden.id,
            estado=orden.estado,
            patente=patente,
            total=orden.total,
            creada_en=orden.creada_en,
            mecanico_id=orden.mecanico_id,
            falla=orden.falla,
            cliente=cliente_nombre,
        )

    async def crear_orden(
        self, data: CrearOrdenRequest, usuario: Usuario
    ) -> OrdenDetalleResponse:
        async with self.uow:
            # RN-19: Si el catálogo de estados está vacío, error 409 con mensaje propio
            total_estados = await self.uow.estados.count()
            if total_estados == 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El catálogo de estados de orden está vacío",
                )

            # RN-16: El vehículo no debe estar dado de baja
            vehiculo = await self.uow.vehiculos.get_by_id(data.vehiculo_id)
            if not vehiculo:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"El vehículo con id {data.vehiculo_id} no existe o está dado de baja",
                )

            # Validar y calcular precios de repuestos (RN-10)
            items_a_crear = []
            total_calculado = 0

            for it in data.items:
                repuesto = await self.uow.repuestos.get_by_id(it.repuesto_id)
                if not repuesto:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"El repuesto con id {it.repuesto_id} no existe o está dado de baja",
                    )
                subtotal = repuesto.precio * it.cantidad
                total_calculado += subtotal
                items_a_crear.append((repuesto, it.cantidad, repuesto.precio))

            now = datetime.now(timezone.utc)
            orden = OrdenTrabajo(
                vehiculo_id=vehiculo.id,
                mecanico_id=None,
                estado="PENDIENTE",
                falla=data.falla,
                creada_en=now,
                total=total_calculado,
            )
            await self.uow.ordenes.add(orden)

            for repuesto, cantidad, precio_unitario in items_a_crear:
                item_orden = ItemOrden(
                    orden_id=orden.id,
                    repuesto_id=repuesto.id,
                    cantidad=cantidad,
                    precio_unitario=precio_unitario,
                )
                await self.uow.items.add(item_orden)

            # Primera línea de historial (RN-10)
            hist = HistorialEstadoOrden(
                orden_id=orden.id,
                desde_estado=None,
                hasta_estado="PENDIENTE",
                usuario_id=usuario.id,
                cuando=now,
            )
            await self.uow.historial.add(hist)

            orden_detalle = await self.uow.ordenes.get_detalle_by_id(orden.id)
            return self._to_orden_detalle_response(orden_detalle)

    async def listar_ordenes(
        self, estado: Optional[str], page: int, size: int
    ) -> PaginatedResponse[OrdenListItemResponse]:
        async with self.uow:
            skip = (page - 1) * size
            items, total = await self.uow.ordenes.get_paginated(estado, skip, size)
            responses = [self._to_orden_list_item(o) for o in items]
            return paginate(responses, total=total, page=page, size=size)

    async def get_orden_detalle(
        self, orden_id: int, usuario: Usuario, roles_vigentes: list[str]
    ) -> OrdenDetalleResponse:
        async with self.uow:
            orden = await self.uow.ordenes.get_detalle_by_id(orden_id)
            if not orden:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Orden de trabajo no encontrada",
                )

            # Verificación de permisos (RN-17): Personal o dueño del vehículo
            es_personal = any(r in ["ADMIN", "RECEPCION", "MECANICO"] for r in roles_vigentes)
            if not es_personal:
                cliente = await self.uow.clientes.get_by_usuario_id(usuario.id)
                es_duenio = (
                    cliente is not None
                    and orden.vehiculo is not None
                    and orden.vehiculo.cliente_id == cliente.id
                )
                if not es_duenio:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="No tiene permiso para ver esta orden de trabajo",
                    )

            return self._to_orden_detalle_response(orden)

    async def iniciar_orden(
        self, orden_id: int, mecanico: Usuario
    ) -> OrdenDetalleResponse:
        async with self.uow:
            orden = await self.uow.ordenes.get_detalle_by_id(orden_id)
            if not orden:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Orden de trabajo no encontrada",
                )

            # RN-11: Transición PENDIENTE -> EN_REPARACION
            if orden.estado != "PENDIENTE":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"No se puede iniciar una orden en estado {orden.estado}",
                )

            now = datetime.now(timezone.utc)
            orden.estado = "EN_REPARACION"
            orden.mecanico_id = mecanico.id
            await self.uow.ordenes.update(orden)

            hist = HistorialEstadoOrden(
                orden_id=orden.id,
                desde_estado="PENDIENTE",
                hasta_estado="EN_REPARACION",
                usuario_id=mecanico.id,
                cuando=now,
            )
            await self.uow.historial.add(hist)

            orden_detalle = await self.uow.ordenes.get_detalle_by_id(orden.id)
            return self._to_orden_detalle_response(orden_detalle)

    async def terminar_orden(
        self,
        orden_id: int,
        usuario: Usuario,
        roles_vigentes: list[str],
        background_tasks: BackgroundTasks,
    ) -> OrdenDetalleResponse:
        async with self.uow:
            orden = await self.uow.ordenes.get_detalle_by_id(orden_id)
            if not orden:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Orden de trabajo no encontrada",
                )

            # RN-11: Sólo el mecánico asignado o un ADMIN pueden terminarla
            es_admin = "ADMIN" in roles_vigentes
            es_mecanico_asignado = orden.mecanico_id == usuario.id
            if not (es_admin or es_mecanico_asignado):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Sólo el mecánico asignado o un administrador pueden terminar la orden",
                )

            if orden.estado != "EN_REPARACION":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"No se puede terminar una orden en estado {orden.estado}",
                )

            # RN-13: Descontar stock de cada ítem en un solo Unit of Work
            # Si un repuesto no alcanza, aborta todo con 409
            for it in orden.items:
                try:
                    await self.uow.repuestos.modify_stock(
                        repuesto_id=it.repuesto_id,
                        delta=-it.cantidad,
                        usuario_id=usuario.id,
                        motivo=f"Salida por orden #{orden.id}",
                        orden_id=orden.id,
                    )
                except ValueError as e:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=str(e),
                    )

            now = datetime.now(timezone.utc)
            orden.estado = "TERMINADA"
            await self.uow.ordenes.update(orden)

            hist = HistorialEstadoOrden(
                orden_id=orden.id,
                desde_estado="EN_REPARACION",
                hasta_estado="TERMINADA",
                usuario_id=usuario.id,
                cuando=now,
            )
            await self.uow.historial.add(hist)

            cliente_nombre = (
                orden.vehiculo.cliente.nombre
                if orden.vehiculo and orden.vehiculo.cliente
                else "Cliente"
            )
            # Agenda aviso con BackgroundTasks (Ejercicio 8)
            background_tasks.add_task(
                notificar_cliente_orden_terminada, orden.id, cliente_nombre
            )

            orden_detalle = await self.uow.ordenes.get_detalle_by_id(orden.id)
            return self._to_orden_detalle_response(orden_detalle)

    async def cancelar_orden(
        self, orden_id: int, usuario: Usuario, roles_vigentes: list[str]
    ) -> OrdenDetalleResponse:
        """
        RN-12: Cancelan la orden la recepción, el administrador o el dueño del vehículo.
        El permiso se evalúa antes que el estado (403 antes que 409).
        """
        async with self.uow:
            orden = await self.uow.ordenes.get_detalle_by_id(orden_id)
            if not orden:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Orden de trabajo no encontrada",
                )

            # 1. Evaluar permisos ANTES del estado (RN-12)
            tiene_rol = any(r in ["RECEPCION", "ADMIN"] for r in roles_vigentes)
            es_duenio = False
            if not tiene_rol:
                cliente = await self.uow.clientes.get_by_usuario_id(usuario.id)
                if (
                    cliente
                    and orden.vehiculo
                    and orden.vehiculo.cliente_id == cliente.id
                ):
                    es_duenio = True

            if not (tiene_rol or es_duenio):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tiene permiso para cancelar esta orden",
                )

            # 2. Evaluar estado (debe estar en PENDIENTE)
            if orden.estado != "PENDIENTE":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"No se puede cancelar una orden en estado {orden.estado}",
                )

            now = datetime.now(timezone.utc)
            orden.estado = "CANCELADA"
            await self.uow.ordenes.update(orden)

            hist = HistorialEstadoOrden(
                orden_id=orden.id,
                desde_estado="PENDIENTE",
                hasta_estado="CANCELADA",
                usuario_id=usuario.id,
                cuando=now,
            )
            await self.uow.historial.add(hist)

            orden_detalle = await self.uow.ordenes.get_detalle_by_id(orden.id)
            return self._to_orden_detalle_response(orden_detalle)

    async def get_estados_orden(self) -> list[EstadoOrden]:
        async with self.uow:
            return list(await self.uow.estados.get_all_ordered())

    async def get_mis_ordenes(
        self, usuario: Usuario, page: int, size: int
    ) -> PaginatedResponse[OrdenListItemResponse]:
        async with self.uow:
            cliente = await self.uow.clientes.get_by_usuario_id(usuario.id)
            if not cliente:
                return paginate([], total=0, page=page, size=size)

            skip = (page - 1) * size
            items, total = await self.uow.ordenes.get_by_cliente_id_paginated(
                cliente.id, skip, size
            )
            responses = [self._to_orden_list_item(o) for o in items]
            return paginate(responses, total=total, page=page, size=size)
