from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def validate_password_bytes(v: str) -> str:
    if len(v.encode("utf-8")) > 72:
        raise ValueError("La contraseña no puede superar los 72 bytes")
    return v


class RolEnum(str, Enum):
    ADMIN = "ADMIN"
    RECEPCION = "RECEPCION"
    MECANICO = "MECANICO"
    CLIENTE = "CLIENTE"


class RegistroRequest(BaseModel):
    email: EmailStr
    nombre: str = Field(min_length=1)
    password: str = Field(min_length=1)
    documento: str = Field(min_length=1)
    telefono: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")

    @field_validator("password")
    @classmethod
    def check_password_bytes(cls, v: str) -> str:
        return validate_password_bytes(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")

    @field_validator("password")
    @classmethod
    def check_password_bytes(cls, v: str) -> str:
        return validate_password_bytes(v)


class LoginResponse(BaseModel):
    mensaje: str
    debe_cambiar_password: bool
    expira_en_segundos: int


class CambiarPasswordRequest(BaseModel):
    password_actual: str = Field(min_length=1)
    password_nueva: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")

    @field_validator("password_actual", "password_nueva")
    @classmethod
    def check_password_bytes(cls, v: str) -> str:
        return validate_password_bytes(v)


class UsuarioResponse(BaseModel):
    id: int
    email: str
    nombre: str
    activo: bool
    debe_cambiar_password: bool
    password_cambiada_en: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UsuarioYoResponse(BaseModel):
    usuario: UsuarioResponse
    roles_vigentes: list[str]
    roles_token: list[str]


class AltaPersonalRequest(BaseModel):
    email: EmailStr
    nombre: str = Field(min_length=1)
    password_provisoria: str = Field(min_length=1)
    rol: RolEnum

    model_config = ConfigDict(extra="forbid")

    @field_validator("password_provisoria")
    @classmethod
    def check_password_bytes(cls, v: str) -> str:
        return validate_password_bytes(v)


class AsignarRolRequest(BaseModel):
    rol: RolEnum
    vence_en: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("vence_en")
    @classmethod
    def check_vence_en(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None:
            if v.tzinfo is None:
                raise ValueError("La fecha de vencimiento debe incluir zona horaria")
            if v <= datetime.now(timezone.utc):
                raise ValueError("La fecha de vencimiento debe ser una fecha futura")
        return v


class AsignacionRolResponse(BaseModel):
    id: int
    usuario_id: int
    rol: str
    desde: datetime
    vence_en: Optional[datetime] = None
    revocada_en: Optional[datetime] = None
    otorgada_por: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class EventoSeguridadResponse(BaseModel):
    id: int
    cuando: datetime
    actor: str
    accion: str

    model_config = ConfigDict(from_attributes=True)
