from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import CheckConstraint, Column, DateTime, Index, text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.clientes.models import Cliente


class Usuario(SQLModel, table=True):
    __tablename__ = "usuario"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, nullable=False)
    nombre: str = Field(nullable=False)
    password_hash: str = Field(nullable=False)
    activo: bool = Field(default=True, nullable=False)
    debe_cambiar_password: bool = Field(default=False, nullable=False)
    password_cambiada_en: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    roles: list["AsignacionRol"] = Relationship(
        back_populates="usuario",
        sa_relationship_kwargs={"foreign_keys": "[AsignacionRol.usuario_id]"},
    )
    cliente: Optional["Cliente"] = Relationship(
        back_populates="usuario",
        sa_relationship_kwargs={"uselist": False},
    )


class AsignacionRol(SQLModel, table=True):
    __tablename__ = "asignacion_rol"

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True, nullable=False)
    rol: str = Field(nullable=False)
    desde: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    vence_en: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    revocada_en: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    otorgada_por: Optional[int] = Field(
        default=None,
        foreign_key="usuario.id",
        index=True,
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "rol IN ('ADMIN', 'RECEPCION', 'MECANICO', 'CLIENTE')",
            name="ck_asignacion_rol_rol",
        ),
        Index(
            "ix_asignacion_rol_usuario_rol_vigente",
            "usuario_id",
            "rol",
            unique=True,
            postgresql_where=text("revocada_en IS NULL"),
        ),
    )

    usuario: Optional[Usuario] = Relationship(
        back_populates="roles",
        sa_relationship_kwargs={"foreign_keys": "[AsignacionRol.usuario_id]"},
    )


class IntentoAcceso(SQLModel, table=True):
    __tablename__ = "intento_acceso"

    id: Optional[int] = Field(default=None, primary_key=True)
    cuando: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    email: str = Field(nullable=False)
    ip: str = Field(nullable=False)
    exito: bool = Field(nullable=False)

    __table_args__ = (
        Index("ix_intento_acceso_email_ip_cuando", "email", "ip", "cuando"),
    )


class EventoSeguridad(SQLModel, table=True):
    __tablename__ = "evento_seguridad"

    id: Optional[int] = Field(default=None, primary_key=True)
    cuando: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    actor: str = Field(nullable=False)
    accion: str = Field(nullable=False)
