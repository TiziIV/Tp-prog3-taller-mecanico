from typing import Sequence
from fastapi import HTTPException, status
from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.clientes.schemas import (
    ClienteDetalleResponse,
    ClienteResponse,
    CrearClienteRequest,
    CrearVehiculoRequest,
    VehiculoResponse,
)
from app.modules.clientes.unit_of_work import ClientesUnitOfWork
from app.modules.usuarios.models import Usuario


class ClientesService:
    def __init__(self, uow: ClientesUnitOfWork):
        self.uow = uow

    async def crear_cliente(self, data: CrearClienteRequest) -> ClienteResponse:
        async with self.uow:
            existente_doc = await self.uow.clientes.get_by_documento(data.documento)
            if existente_doc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El documento ya pertenece a un cliente del taller",
                )

            if data.usuario_id is not None:
                existente_user = await self.uow.clientes.get_by_usuario_id(data.usuario_id)
                if existente_user:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="El usuario ya posee una ficha de cliente asignada",
                    )

            cliente = Cliente(
                usuario_id=data.usuario_id,
                nombre=data.nombre,
                documento=data.documento,
                telefono=data.telefono,
            )
            await self.uow.clientes.add(cliente)
            return ClienteResponse.model_validate(cliente)

    async def get_cliente_detalle(self, cliente_id: int) -> ClienteDetalleResponse:
        async with self.uow:
            cliente = await self.uow.clientes.get_by_id_with_vehiculos(cliente_id)
            if not cliente:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Cliente no encontrado",
                )
            return ClienteDetalleResponse.model_validate(cliente)

    async def crear_vehiculo(
        self, cliente_id: int, data: CrearVehiculoRequest
    ) -> VehiculoResponse:
        async with self.uow:
            cliente = await self.uow.clientes.get_by_id(cliente_id)
            if not cliente:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Cliente no encontrado",
                )

            # Verificar si existe una patente vigente (RN-01 y RN-16)
            existente = await self.uow.vehiculos.get_by_patente_activa(data.patente)
            if existente:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe un vehículo activo registrado con la patente {data.patente}",
                )

            vehiculo = Vehiculo(
                cliente_id=cliente_id,
                patente=data.patente,
                marca=data.marca,
                modelo=data.modelo,
                anio=data.anio,
                borrado_en=None,
            )
            await self.uow.vehiculos.add(vehiculo)
            return VehiculoResponse.model_validate(vehiculo)

    async def dar_de_baja_vehiculo(self, vehiculo_id: int) -> None:
        async with self.uow:
            vehiculo = await self.uow.vehiculos.get_by_id(vehiculo_id)
            if not vehiculo:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Vehículo no encontrado",
                )

            # RN-16: Un vehículo con órdenes abiertas no se da de baja
            ordenes_abiertas = await self.uow.vehiculos.count_open_orders(vehiculo_id)
            if ordenes_abiertas > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No se puede dar de baja un vehículo con órdenes abiertas",
                )

            await self.uow.vehiculos.soft_delete(vehiculo)

    async def get_mis_vehiculos(self, usuario: Usuario) -> Sequence[Vehiculo]:
        async with self.uow:
            cliente = await self.uow.clientes.get_by_usuario_id(usuario.id)
            if not cliente:
                return []
            return await self.uow.vehiculos.get_by_cliente_id(cliente.id)
