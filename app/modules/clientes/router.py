from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.core.dependencies import (
    get_usuario_actual,
    requiere_rol,
    verificar_password_no_pendiente,
)
from app.modules.clientes.schemas import (
    ClienteDetalleResponse,
    ClienteResponse,
    CrearClienteRequest,
    CrearVehiculoRequest,
    VehiculoResponse,
)
from app.modules.clientes.service import ClientesService
from app.modules.clientes.unit_of_work import ClientesUnitOfWork
from app.modules.usuarios.models import Usuario

clientes_router = APIRouter(tags=["Clientes y Vehículos"])


def get_clientes_service(
    session: AsyncSession = Depends(get_session),
) -> ClientesService:
    uow = ClientesUnitOfWork(session)
    return ClientesService(uow)


@clientes_router.post(
    "/clientes",
    response_model=ClienteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_cliente(
    data: CrearClienteRequest,
    _: Usuario = Depends(requiere_rol("RECEPCION", "ADMIN")),
    service: ClientesService = Depends(get_clientes_service),
) -> ClienteResponse:
    return await service.crear_cliente(data)


@clientes_router.get(
    "/clientes/{id}",
    response_model=ClienteDetalleResponse,
    status_code=status.HTTP_200_OK,
)
async def get_cliente(
    id: int,
    _: Usuario = Depends(requiere_rol("RECEPCION", "ADMIN")),
    service: ClientesService = Depends(get_clientes_service),
) -> ClienteDetalleResponse:
    return await service.get_cliente_detalle(id)


@clientes_router.post(
    "/clientes/{id}/vehiculos",
    response_model=VehiculoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_vehiculo(
    id: int,
    data: CrearVehiculoRequest,
    _: Usuario = Depends(requiere_rol("RECEPCION", "ADMIN")),
    service: ClientesService = Depends(get_clientes_service),
) -> VehiculoResponse:
    return await service.crear_vehiculo(id, data)


@clientes_router.delete(
    "/vehiculos/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def dar_de_baja_vehiculo(
    id: int,
    _: Usuario = Depends(requiere_rol("RECEPCION", "ADMIN")),
    service: ClientesService = Depends(get_clientes_service),
) -> None:
    await service.dar_de_baja_vehiculo(id)


@clientes_router.get(
    "/mis-vehiculos",
    response_model=list[VehiculoResponse],
    status_code=status.HTTP_200_OK,
)
async def get_mis_vehiculos(
    usuario: Usuario = Depends(verificar_password_no_pendiente),
    service: ClientesService = Depends(get_clientes_service),
) -> list[VehiculoResponse]:
    vehiculos = await service.get_mis_vehiculos(usuario)
    return [VehiculoResponse.model_validate(v) for v in vehiculos]
