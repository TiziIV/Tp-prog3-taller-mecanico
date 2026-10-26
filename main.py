from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
import uvicorn

from app.core.config import settings
from app.core.database import create_engine, create_session_factory
from app.core.dependencies import verificar_password_no_pendiente
from app.core.security import get_password_hash
from app.modules.clientes.router import clientes_router
from app.modules.health.router import router as health_router
from app.modules.ordenes.router import ordenes_router
from app.modules.repuestos.router import repuestos_router
from app.modules.usuarios.router import auth_router, usuarios_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Ciclo de vida de la aplicación:
    - Crea el motor asincrónico y la fábrica de sesiones y los guarda en app.state (Ejercicio 1).
    - Calcula una sola vez el dummy_hash para mitigar timing attacks en el login (RN-09).
    - Al apagar, cierra el motor limpiamente con dispose().
    """
    engine = create_engine()
    session_factory = create_session_factory(engine)

    app.state.engine = engine
    app.state.session_factory = session_factory

    # Hash ficticio calculado una única vez al inicio
    dummy_hash = await get_password_hash("dummy_mitigation_password_for_timing")
    app.state.dummy_hash = dummy_hash

    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(
    title="Taller Mecánico API",
    description="API para órdenes de trabajo, gestión de repuestos y control de acceso.",
    version="1.0.0",
    lifespan=lifespan,
)


# --- Manejadores de Excepciones Globales (RN-18) ---


@app.exception_handler(IntegrityError)
async def integrity_error_handler(
    request: Request, exc: IntegrityError
) -> JSONResponse:
    """
    Traduce errores de integridad de base de datos a un 409 con mensaje propio,
    impidiendo la fuga de texto interno del esquema (RN-18, sección 4.13).
    """
    error_msg = "Conflicto de integridad de datos: la operación viola una restricción del sistema."
    orig_text = str(exc.orig).lower() if hasattr(exc, "orig") else str(exc).lower()

    if "unique" in orig_text or "duplicate key" in orig_text:
        error_msg = "El registro ya existe o entra en conflicto con un dato existente."
    elif "check constraint" in orig_text or "violates check" in orig_text:
        error_msg = "Los valores proporcionados violan una regla de validación de la base de datos."
    elif "foreign key" in orig_text or "violates foreign key" in orig_text:
        error_msg = "Referencia inválida: el recurso relacionado no existe."

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": error_msg},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Retorna 422 para errores de contrato o parámetros fuera de rango.
    """
    errors = exc.errors()
    # Tomar el primer mensaje o listar detalle amigable
    first_msg = errors[0]["msg"] if errors else "Datos de entrada inválidos"
    if first_msg.startswith("Value error, "):
        first_msg = first_msg[len("Value error, "):]

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": first_msg, "errors": errors},
    )


# --- Montaje de los Dos Grupos de Rutas (RN-06, Sección 5.10) ---

# 1. Grupo Abierto: salud (/health) y autenticación (/auth)
abierto_router = APIRouter()
abierto_router.include_router(health_router)
abierto_router.include_router(auth_router)

# 2. Grupo Protegido: monta el control de cambio obligatorio de contraseña una sola vez
protegido_router = APIRouter(dependencies=[Depends(verificar_password_no_pendiente)])
protegido_router.include_router(usuarios_router)
protegido_router.include_router(clientes_router)
protegido_router.include_router(repuestos_router)
protegido_router.include_router(ordenes_router)

app.include_router(abierto_router)
app.include_router(protegido_router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
