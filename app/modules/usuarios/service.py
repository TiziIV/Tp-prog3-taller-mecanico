from datetime import datetime, timezone
from typing import Optional, Sequence
from fastapi import HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.paginacion import PaginatedResponse, paginate
from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.modules.clientes.models import Cliente
from app.modules.usuarios.models import (
    AsignacionRol,
    EventoSeguridad,
    IntentoAcceso,
    Usuario,
)
from app.modules.usuarios.schemas import (
    AltaPersonalRequest,
    AsignarRolRequest,
    CambiarPasswordRequest,
    EventoSeguridadResponse,
    LoginRequest,
    LoginResponse,
    RegistroRequest,
    UsuarioResponse,
    UsuarioYoResponse,
)
from app.modules.usuarios.unit_of_work import UsuariosUnitOfWork


async def registrar_intento_acceso_independiente(
    session_factory: async_sessionmaker[AsyncSession],
    email: str,
    ip: str,
    exito: bool,
) -> None:
    """
    Registra cada intento de login en intento_acceso usando una sesión y transacción
    propias e independientes que hacen commit siempre (Ejercicio 7, sección 6.8.1).
    Costo: Abre una conexión y transacción adicional exclusivamente para este registro,
    garantizando que la fila no se pierda aunque la petición principal falle o revierta.
    """
    async with session_factory() as session:
        intento = IntentoAcceso(
            cuando=datetime.now(timezone.utc),
            email=email,
            ip=ip,
            exito=exito,
        )
        session.add(intento)
        await session.commit()


class UsuariosService:
    def __init__(self, uow: UsuariosUnitOfWork):
        self.uow = uow

    async def registrar_cliente(self, data: RegistroRequest) -> UsuarioResponse:
        # Calcular hash de contraseña fuera de la transacción (Ejercicio 4)
        hashed_password = await get_password_hash(data.password)

        async with self.uow:
            # RN-01 y RN-02: Verificar unicidad antes o dejar que la base lo garantice,
            # pero respondiendo 409 con mensaje propio sin apropiarse de ficha existente.
            existente_usuario = await self.uow.usuarios.get_by_email(data.email)
            if existente_usuario:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El correo electrónico ya se encuentra registrado",
                )

            existente_cliente = await self.uow.clientes.get_by_documento(data.documento)
            if existente_cliente:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El documento ya pertenece a un cliente del taller",
                )

            now = datetime.now(timezone.utc)
            usuario = Usuario(
                email=data.email,
                nombre=data.nombre,
                password_hash=hashed_password,
                activo=True,
                debe_cambiar_password=False,
                password_cambiada_en=now,
            )
            await self.uow.usuarios.add(usuario)

            # Rol CLIENTE
            asignacion = AsignacionRol(
                usuario_id=usuario.id,
                rol="CLIENTE",
                desde=now,
            )
            await self.uow.roles.add(asignacion)

            # Ficha de cliente
            cliente = Cliente(
                usuario_id=usuario.id,
                nombre=data.nombre,
                documento=data.documento,
                telefono=data.telefono,
            )
            await self.uow.clientes.add(cliente)

            # Evento de seguridad
            evento = EventoSeguridad(
                cuando=now,
                actor=usuario.email,
                accion="Auto-registro de nuevo cliente",
            )
            await self.uow.eventos.add(evento)

            return UsuarioResponse.model_validate(usuario)

    async def login(
        self,
        data: LoginRequest,
        ip: str,
        dummy_hash: str,
        session_factory: async_sessionmaker[AsyncSession],
        response: Response,
    ) -> LoginResponse:
        # 1. Límite de intentos (RN-08): conteo sobre intento_acceso en últimos 60s
        fallos = await self.uow.intentos.count_recent_failures(data.email, ip, window_seconds=60)
        if fallos >= 5:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiados intentos fallidos. Intente nuevamente en 60 segundos.",
                headers={"Retry-After": "60"},
            )

        # 2. Verificación contra hash de usuario o dummy_hash (RN-09)
        usuario = await self.uow.usuarios.get_by_email(data.email)
        es_valido = False

        if usuario and usuario.activo:
            es_valido = await verify_password(data.password, usuario.password_hash)
        else:
            await verify_password(data.password, dummy_hash)
            es_valido = False

        # 3. Anotar intento en sesión y transacción propia (Ejercicio 7)
        await registrar_intento_acceso_independiente(
            session_factory, data.email, ip, exito=es_valido
        )

        if not es_valido or not usuario:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas",
            )

        # 4. Obtener roles vigentes y emitir token
        roles_vigentes = await self.uow.roles.get_roles_vigentes_by_usuario_id(usuario.id)
        roles_nombres = [r.rol for r in roles_vigentes]

        token_data = {
            "sub": str(usuario.id),
            "roles": roles_nombres,
        }
        token = create_access_token(token_data)

        # Configurar cookie HttpOnly
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=settings.JWT_EXPIRATION_SECONDS,
            secure=settings.COOKIE_SECURE,
        )

        return LoginResponse(
            mensaje="Sesión iniciada",
            debe_cambiar_password=usuario.debe_cambiar_password,
            expira_en_segundos=settings.JWT_EXPIRATION_SECONDS,
        )

    async def logout(self, response: Response) -> dict[str, str]:
        response.delete_cookie(key="access_token", httponly=True, samesite="lax")
        return {"mensaje": "Sesión cerrada"}

    async def get_yo(
        self, usuario: Usuario, roles_token: list[str]
    ) -> UsuarioYoResponse:
        roles_vigentes = await self.uow.roles.get_roles_vigentes_by_usuario_id(usuario.id)
        return UsuarioYoResponse(
            usuario=UsuarioResponse.model_validate(usuario),
            roles_vigentes=[r.rol for r in roles_vigentes],
            roles_token=roles_token,
        )

    async def cambiar_password(
        self,
        usuario: Usuario,
        data: CambiarPasswordRequest,
        response: Response,
    ) -> dict[str, str]:
        # Verificar contraseña actual
        valida = await verify_password(data.password_actual, usuario.password_hash)
        if not valida:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="La contraseña actual es incorrecta",
            )

        # Hash de la nueva contraseña fuera de transacción
        nuevo_hash = await get_password_hash(data.password_nueva)

        async with self.uow:
            now = datetime.now(timezone.utc)
            usuario_db = await self.uow.usuarios.get_by_id(usuario.id)
            if not usuario_db:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")

            usuario_db.password_hash = nuevo_hash
            usuario_db.debe_cambiar_password = False
            usuario_db.password_cambiada_en = now
            await self.uow.usuarios.update(usuario_db)

            evento = EventoSeguridad(
                cuando=now,
                actor=usuario_db.email,
                accion="Cambio de contraseña de usuario",
            )
            await self.uow.eventos.add(evento)

            # Emitir nuevo token con fecha posterior a password_cambiada_en (RN-07)
            roles_vigentes = await self.uow.roles.get_roles_vigentes_by_usuario_id(usuario_db.id)
            token_data = {
                "sub": str(usuario_db.id),
                "roles": [r.rol for r in roles_vigentes],
            }
            nuevo_token = create_access_token(token_data)

            response.set_cookie(
                key="access_token",
                value=nuevo_token,
                httponly=True,
                samesite="lax",
                max_age=settings.JWT_EXPIRATION_SECONDS,
                secure=settings.COOKIE_SECURE,
            )

            return {"mensaje": "Contraseña cambiada exitosamente"}

    async def alta_personal(
        self, data: AltaPersonalRequest, admin: Usuario
    ) -> UsuarioResponse:
        hashed_password = await get_password_hash(data.password_provisoria)

        async with self.uow:
            existente = await self.uow.usuarios.get_by_email(data.email)
            if existente:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El correo electrónico ya se encuentra registrado",
                )

            now = datetime.now(timezone.utc)
            usuario = Usuario(
                email=data.email,
                nombre=data.nombre,
                password_hash=hashed_password,
                activo=True,
                debe_cambiar_password=True,  # Personal creado con cambio obligatorio
                password_cambiada_en=None,
            )
            await self.uow.usuarios.add(usuario)

            asignacion = AsignacionRol(
                usuario_id=usuario.id,
                rol=data.rol.value,
                desde=now,
                otorgada_por=admin.id,
            )
            await self.uow.roles.add(asignacion)

            evento = EventoSeguridad(
                cuando=now,
                actor=admin.email,
                accion=f"Alta de personal: {usuario.email} con rol {data.rol.value}",
            )
            await self.uow.eventos.add(evento)

            return UsuarioResponse.model_validate(usuario)

    async def get_roles_usuario(self, usuario_id: int) -> list[AsignacionRol]:
        async with self.uow:
            usuario = await self.uow.usuarios.get_by_id(usuario_id)
            if not usuario:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")
            return await self.uow.roles.get_all_by_usuario_id(usuario_id)

    async def asignar_rol(
        self, usuario_id: int, data: AsignarRolRequest, admin: Usuario
    ) -> AsignacionRol:
        async with self.uow:
            usuario = await self.uow.usuarios.get_by_id(usuario_id)
            if not usuario:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")

            now = datetime.now(timezone.utc)
            # Verificar si existe una asignación abierta para ese rol (RN-03)
            abierta = await self.uow.roles.get_asignacion_abierta(usuario_id, data.rol.value)
            if abierta:
                # Si está abierta y vigente, conflicto 409
                if abierta.vence_en is None or abierta.vence_en > now:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"El usuario ya cuenta con una asignación vigente del rol {data.rol.value}",
                    )
                # Si ya venció, se revoca la anterior para dar paso a la nueva
                abierta.revocada_en = now
                await self.uow.roles.update(abierta)

            nueva_asignacion = AsignacionRol(
                usuario_id=usuario_id,
                rol=data.rol.value,
                desde=now,
                vence_en=data.vence_en,
                otorgada_por=admin.id,
            )
            await self.uow.roles.add(nueva_asignacion)

            evento = EventoSeguridad(
                cuando=now,
                actor=admin.email,
                accion=f"Asignación de rol {data.rol.value} a usuario {usuario.email}",
            )
            await self.uow.eventos.add(evento)

            return nueva_asignacion

    async def revocar_rol(
        self, usuario_id: int, rol: str, admin: Usuario
    ) -> dict[str, str]:
        async with self.uow:
            usuario = await self.uow.usuarios.get_by_id(usuario_id)
            if not usuario:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")

            # Autoprotección (RN-05): un admin no puede revocarse su propio ADMIN
            if admin.id == usuario_id and rol == "ADMIN":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Un administrador no puede revocarse su propio rol ADMIN",
                )

            # El sistema nunca puede quedar sin administradores vigentes
            if rol == "ADMIN":
                total_admins = await self.uow.usuarios.count_active_admins()
                if total_admins <= 1:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="No se puede revocar el rol: el sistema debe mantener al menos un administrador vigente",
                    )

            now = datetime.now(timezone.utc)
            roles_vigentes = await self.uow.roles.get_roles_vigentes_by_usuario_id(usuario_id)
            asignacion = next((r for r in roles_vigentes if r.rol == rol), None)

            if not asignacion:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"El usuario no tiene una asignación vigente del rol {rol}",
                )

            asignacion.revocada_en = now
            await self.uow.roles.update(asignacion)

            evento = EventoSeguridad(
                cuando=now,
                actor=admin.email,
                accion=f"Revocación de rol {rol} a usuario {usuario.email}",
            )
            await self.uow.eventos.add(evento)

            return {"mensaje": f"Rol {rol} revocado exitosamente"}

    async def get_eventos_seguridad(
        self, page: int, size: int
    ) -> PaginatedResponse[EventoSeguridadResponse]:
        async with self.uow:
            skip = (page - 1) * size
            items, total = await self.uow.eventos.get_paginated(skip=skip, limit=size)
            responses = [EventoSeguridadResponse.model_validate(e) for e in items]
            return paginate(responses, total=total, page=page, size=size)
