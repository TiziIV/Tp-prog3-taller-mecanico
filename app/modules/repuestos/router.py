from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.core.dependencies import requiere_rol
from app.core.paginacion import PaginatedResponse
from app.modules.repuestos.schemas import (
    ActualizarRepuestoRequest,
    CrearRepuestoRequest,
    HistorialPrecioResponse,
    MovimientoStockResponse,
    ReponerRepuestoRequest,
    RepuestoResponse,
)
from app.modules.repuestos.service import RepuestosService
from app.modules.repuestos.unit_of_work import RepuestosUnitOfWork
from app.modules.usuarios.models import Usuario

repuestos_router = APIRouter(prefix="/repuestos", tags=["Repuestos y Stock"])


def get_repuestos_service(
    session: AsyncSession = Depends(get_session),
) -> RepuestosService:
    uow = RepuestosUnitOfWork(session)
    return RepuestosService(uow)


@repuestos_router.get(
    "",
    response_model=PaginatedResponse[RepuestoResponse],
    status_code=status.HTTP_200_OK,
)
async def listar_repuestos(
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    _: Usuario = Depends(requiere_rol("ADMIN", "RECEPCION", "MECANICO")),
    service: RepuestosService = Depends(get_repuestos_service),
) -> PaginatedResponse[RepuestoResponse]:
    return await service.listar_repuestos(q, page, size)


@repuestos_router.get(
    "/{id}",
    response_model=RepuestoResponse,
    status_code=status.HTTP_200_OK,
)
async def get_repuesto(
    id: int,
    _: Usuario = Depends(requiere_rol("ADMIN", "RECEPCION", "MECANICO")),
    service: RepuestosService = Depends(get_repuestos_service),
) -> RepuestoResponse:
    return await service.get_repuesto(id)


@repuestos_router.post(
    "",
    response_model=RepuestoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_repuesto(
    data: CrearRepuestoRequest,
    admin: Usuario = Depends(requiere_rol("ADMIN")),
    service: RepuestosService = Depends(get_repuestos_service),
) -> RepuestoResponse:
    return await service.crear_repuesto(data, admin)


@repuestos_router.patch(
    "/{id}",
    response_model=RepuestoResponse,
    status_code=status.HTTP_200_OK,
)
async def actualizar_repuesto(
    id: int,
    data: ActualizarRepuestoRequest,
    admin: Usuario = Depends(requiere_rol("ADMIN")),
    service: RepuestosService = Depends(get_repuestos_service),
) -> RepuestoResponse:
    return await service.actualizar_repuesto(id, data, admin)


@repuestos_router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def dar_de_baja_repuesto(
    id: int,
    _: Usuario = Depends(requiere_rol("ADMIN")),
    service: RepuestosService = Depends(get_repuestos_service),
) -> None:
    await service.dar_de_baja_repuesto(id)


@repuestos_router.post(
    "/{id}/reponer",
    response_model=RepuestoResponse,
    status_code=status.HTTP_200_OK,
)
async def reponer_stock(
    id: int,
    data: ReponerRepuestoRequest,
    admin: Usuario = Depends(requiere_rol("ADMIN")),
    service: RepuestosService = Depends(get_repuestos_service),
) -> RepuestoResponse:
    return await service.reponer_stock(id, data, admin)


@repuestos_router.get(
    "/{id}/movimientos",
    response_model=list[MovimientoStockResponse],
    status_code=status.HTTP_200_OK,
)
async def get_movimientos(
    id: int,
    _: Usuario = Depends(requiere_rol("ADMIN")),
    service: RepuestosService = Depends(get_repuestos_service),
) -> list[MovimientoStockResponse]:
    movimientos = await service.get_movimientos(id)
    return [MovimientoStockResponse.model_validate(m) for m in movimientos]


@repuestos_router.get(
    "/{id}/precios",
    response_model=list[HistorialPrecioResponse],
    status_code=status.HTTP_200_OK,
)
async def get_precios(
    id: int,
    _: Usuario = Depends(requiere_rol("ADMIN")),
    service: RepuestosService = Depends(get_repuestos_service),
) -> list[HistorialPrecioResponse]:
    precios = await service.get_historial_precios(id)
    return [HistorialPrecioResponse.model_validate(p) for p in precios]
