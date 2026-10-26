from typing import Optional
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.core.dependencies import (
    requiere_rol,
    verificar_password_no_pendiente,
)
from app.core.paginacion import PaginatedResponse
from app.modules.ordenes.schemas import (
    CrearOrdenRequest,
    EstadoOrdenEnum,
    EstadoOrdenResponse,
    OrdenDetalleResponse,
    OrdenListItemResponse,
)
from app.modules.ordenes.service import OrdenesService
from app.modules.ordenes.unit_of_work import OrdenesUnitOfWork
from app.modules.usuarios.models import Usuario
from app.modules.usuarios.repository import AsignacionRolRepository

ordenes_router = APIRouter(tags=["Órdenes de Trabajo"])


def get_ordenes_service(
    session: AsyncSession = Depends(get_session),
) -> OrdenesService:
    uow = OrdenesUnitOfWork(session)
    return OrdenesService(uow)


async def get_roles_vigentes(
    usuario: Usuario = Depends(verificar_password_no_pendiente),
    session: AsyncSession = Depends(get_session),
) -> list[str]:
    repo = AsignacionRolRepository(session)
    asignaciones = await repo.get_roles_vigentes_by_usuario_id(usuario.id)
    return [a.rol for a in asignaciones]


@ordenes_router.post(
    "/ordenes",
    response_model=OrdenDetalleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_orden(
    data: CrearOrdenRequest,
    usuario: Usuario = Depends(requiere_rol("RECEPCION", "ADMIN")),
    service: OrdenesService = Depends(get_ordenes_service),
) -> OrdenDetalleResponse:
    return await service.crear_orden(data, usuario)


@ordenes_router.get(
    "/ordenes",
    response_model=PaginatedResponse[OrdenListItemResponse],
    status_code=status.HTTP_200_OK,
)
async def listar_ordenes(
    estado: Optional[EstadoOrdenEnum] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    _: Usuario = Depends(requiere_rol("ADMIN", "RECEPCION", "MECANICO")),
    service: OrdenesService = Depends(get_ordenes_service),
) -> PaginatedResponse[OrdenListItemResponse]:
    estado_str = estado.value if estado else None
    return await service.listar_ordenes(estado_str, page, size)


@ordenes_router.get(
    "/ordenes/{id}",
    response_model=OrdenDetalleResponse,
    status_code=status.HTTP_200_OK,
)
async def get_orden(
    id: int,
    usuario: Usuario = Depends(verificar_password_no_pendiente),
    roles_vigentes: list[str] = Depends(get_roles_vigentes),
    service: OrdenesService = Depends(get_ordenes_service),
) -> OrdenDetalleResponse:
    return await service.get_orden_detalle(id, usuario, roles_vigentes)


@ordenes_router.post(
    "/ordenes/{id}/iniciar",
    response_model=OrdenDetalleResponse,
    status_code=status.HTTP_200_OK,
)
async def iniciar_orden(
    id: int,
    mecanico: Usuario = Depends(requiere_rol("MECANICO")),
    service: OrdenesService = Depends(get_ordenes_service),
) -> OrdenDetalleResponse:
    return await service.iniciar_orden(id, mecanico)


@ordenes_router.post(
    "/ordenes/{id}/terminar",
    response_model=OrdenDetalleResponse,
    status_code=status.HTTP_200_OK,
)
async def terminar_orden(
    id: int,
    background_tasks: BackgroundTasks,
    usuario: Usuario = Depends(verificar_password_no_pendiente),
    roles_vigentes: list[str] = Depends(get_roles_vigentes),
    service: OrdenesService = Depends(get_ordenes_service),
) -> OrdenDetalleResponse:
    return await service.terminar_orden(
        id, usuario, roles_vigentes, background_tasks
    )


# NOTA: Esta ruta NO lleva requiere_rol en el router porque el dueño
# del vehículo puede cancelarla sin rol de personal (RN-12).
@ordenes_router.post(
    "/ordenes/{id}/cancelar",
    response_model=OrdenDetalleResponse,
    status_code=status.HTTP_200_OK,
)
async def cancelar_orden(
    id: int,
    usuario: Usuario = Depends(verificar_password_no_pendiente),
    roles_vigentes: list[str] = Depends(get_roles_vigentes),
    service: OrdenesService = Depends(get_ordenes_service),
) -> OrdenDetalleResponse:
    return await service.cancelar_orden(id, usuario, roles_vigentes)


@ordenes_router.get(
    "/estados-orden",
    response_model=list[EstadoOrdenResponse],
    status_code=status.HTTP_200_OK,
)
async def get_estados_orden(
    _: Usuario = Depends(verificar_password_no_pendiente),
    service: OrdenesService = Depends(get_ordenes_service),
) -> list[EstadoOrdenResponse]:
    estados = await service.get_estados_orden()
    return [EstadoOrdenResponse.model_validate(e) for e in estados]


@ordenes_router.get(
    "/mis-ordenes",
    response_model=PaginatedResponse[OrdenListItemResponse],
    status_code=status.HTTP_200_OK,
)
async def get_mis_ordenes(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    usuario: Usuario = Depends(verificar_password_no_pendiente),
    service: OrdenesService = Depends(get_ordenes_service),
) -> PaginatedResponse[OrdenListItemResponse]:
    return await service.get_mis_ordenes(usuario, page, size)
