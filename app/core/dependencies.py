from typing import Callable, Optional
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.core.security import decode_access_token
from app.modules.usuarios.models import Usuario
from app.modules.usuarios.repository import AsignacionRolRepository


async def get_usuario_actual(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Usuario:
    """
    Lee la cookie access_token.
    Responde 401 si no hay cookie, si el token es inválido o venció,
    si el usuario no existe o está inactivo, o si el token es anterior
    al último cambio de contraseña (RN-07).
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado: falta cookie de sesión",
        )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no contiene identificador de usuario",
        )

    usuario = await session.get(Usuario, int(sub))
    if not usuario or not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inexistente o inactivo",
        )

    if usuario.password_cambiada_en is not None:
        token_iat = payload.get("iat")
        pwd_cambiada_timestamp = usuario.password_cambiada_en.timestamp()
        # Comparación sin truncar a segundos (RN-07)
        if token_iat is None or float(token_iat) < pwd_cambiada_timestamp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión expirada por cambio de contraseña",
            )

    # Almacenar en request.state para que endpoints como /auth/yo puedan leer los claims del token
    request.state.jwt_payload = payload
    return usuario


async def verificar_password_no_pendiente(
    usuario: Usuario = Depends(get_usuario_actual),
) -> Usuario:
    """
    Control de cambio obligatorio de contraseña montado en el grupo protegido (RN-06).
    Si debe_cambiar_password es True, bloquea el acceso con 403.
    """
    if usuario.debe_cambiar_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debe cambiar su contraseña antes de continuar",
        )
    return usuario


def requiere_rol(*roles_permitidos: str) -> Callable:
    """
    Consulta los roles vigentes en la base de datos en cada petición (RN-04).
    Si el usuario no tiene al menos uno de los roles vigentes indicados, responde 403.
    """
    async def role_checker(
        usuario: Usuario = Depends(verificar_password_no_pendiente),
        session: AsyncSession = Depends(get_session),
    ) -> Usuario:
        repo = AsignacionRolRepository(session)
        roles_vigentes = await repo.get_roles_vigentes_by_usuario_id(usuario.id)
        nombres_roles = [r.rol for r in roles_vigentes]
        if not any(r in roles_permitidos for r in nombres_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso denegado: se requiere uno de los roles {roles_permitidos}",
            )
        return usuario

    return role_checker
