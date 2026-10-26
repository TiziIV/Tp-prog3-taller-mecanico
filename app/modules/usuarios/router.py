from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.core.dependencies import (
    get_usuario_actual,
    requiere_rol,
)
from app.core.paginacion import PaginatedResponse
from app.modules.usuarios.models import Usuario
from app.modules.usuarios.schemas import (
    AltaPersonalRequest,
    AsignacionRolResponse,
    AsignarRolRequest,
    CambiarPasswordRequest,
    EventoSeguridadResponse,
    LoginRequest,
    LoginResponse,
    RegistroRequest,
    UsuarioResponse,
    UsuarioYoResponse,
)
from app.modules.usuarios.service import UsuariosService
from app.modules.usuarios.unit_of_work import UsuariosUnitOfWork

# Router del grupo abierto: /auth/*
auth_router = APIRouter(prefix="/auth", tags=["Autenticación"])

# Router del grupo protegido: /usuarios/* y /eventos
usuarios_router = APIRouter(tags=["Usuarios y Seguridad"])


def get_usuarios_service(
    session: AsyncSession = Depends(get_session),
) -> UsuariosService:
    uow = UsuariosUnitOfWork(session)
    return UsuariosService(uow)


# --- Endpoints Grupo Abierto (/auth) ---


@auth_router.post(
    "/registro",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
)
async def registro(
    data: RegistroRequest,
    service: UsuariosService = Depends(get_usuarios_service),
) -> UsuarioResponse:
    return await service.registrar_cliente(data)


@auth_router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    service: UsuariosService = Depends(get_usuarios_service),
) -> LoginResponse:
    ip = request.client.host if request.client else "127.0.0.1"
    dummy_hash = getattr(request.app.state, "dummy_hash", "")
    session_factory = request.app.state.session_factory
    return await service.login(
        data=data,
        ip=ip,
        dummy_hash=dummy_hash,
        session_factory=session_factory,
        response=response,
    )


@auth_router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
)
async def logout(
    response: Response,
    service: UsuariosService = Depends(get_usuarios_service),
) -> dict[str, str]:
    return await service.logout(response)


@auth_router.get(
    "/yo",
    response_model=UsuarioYoResponse,
    status_code=status.HTTP_200_OK,
)
async def yo(
    request: Request,
    usuario: Usuario = Depends(get_usuario_actual),
    service: UsuariosService = Depends(get_usuarios_service),
) -> UsuarioYoResponse:
    jwt_payload = getattr(request.state, "jwt_payload", {})
    roles_token = jwt_payload.get("roles", [])
    return await service.get_yo(usuario, roles_token)


@auth_router.post(
    "/cambiar-password",
    status_code=status.HTTP_200_OK,
)
async def cambiar_password(
    data: CambiarPasswordRequest,
    response: Response,
    usuario: Usuario = Depends(get_usuario_actual),
    service: UsuariosService = Depends(get_usuarios_service),
) -> dict[str, str]:
    return await service.cambiar_password(usuario, data, response)


# --- Endpoints Grupo Protegido (/usuarios y /eventos) ---


@usuarios_router.post(
    "/usuarios",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
)
async def alta_personal(
    data: AltaPersonalRequest,
    admin: Usuario = Depends(requiere_rol("ADMIN")),
    service: UsuariosService = Depends(get_usuarios_service),
) -> UsuarioResponse:
    return await service.alta_personal(data, admin)


@usuarios_router.get(
    "/usuarios/{id}/roles",
    response_model=list[AsignacionRolResponse],
    status_code=status.HTTP_200_OK,
)
async def get_roles_usuario(
    id: int,
    _: Usuario = Depends(requiere_rol("ADMIN")),
    service: UsuariosService = Depends(get_usuarios_service),
) -> list[AsignacionRolResponse]:
    roles = await service.get_roles_usuario(id)
    return [AsignacionRolResponse.model_validate(r) for r in roles]


@usuarios_router.post(
    "/usuarios/{id}/roles",
    response_model=AsignacionRolResponse,
    status_code=status.HTTP_201_CREATED,
)
async def asignar_rol(
    id: int,
    data: AsignarRolRequest,
    admin: Usuario = Depends(requiere_rol("ADMIN")),
    service: UsuariosService = Depends(get_usuarios_service),
) -> AsignacionRolResponse:
    rol = await service.asignar_rol(id, data, admin)
    return AsignacionRolResponse.model_validate(rol)


@usuarios_router.delete(
    "/usuarios/{id}/roles/{rol}",
    status_code=status.HTTP_200_OK,
)
async def revocar_rol(
    id: int,
    rol: str,
    admin: Usuario = Depends(requiere_rol("ADMIN")),
    service: UsuariosService = Depends(get_usuarios_service),
) -> dict[str, str]:
    return await service.revocar_rol(id, rol, admin)


@usuarios_router.get(
    "/eventos",
    response_model=PaginatedResponse[EventoSeguridadResponse],
    status_code=status.HTTP_200_OK,
)
async def get_eventos(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    _: Usuario = Depends(requiere_rol("ADMIN")),
    service: UsuariosService = Depends(get_usuarios_service),
) -> PaginatedResponse[EventoSeguridadResponse]:
    return await service.get_eventos_seguridad(page, size)
