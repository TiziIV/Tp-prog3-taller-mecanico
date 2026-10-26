from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import CheckConstraint, Column, DateTime, Index, text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.usuarios.models import Usuario
    from app.modules.ordenes.models import OrdenTrabajo


class Cliente(SQLModel, table=True):
    __tablename__ = "cliente"

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: Optional[int] = Field(
        default=None,
        foreign_key="usuario.id",
        unique=True,
        index=True,
        nullable=True,
    )
    nombre: str = Field(nullable=False)
    documento: str = Field(unique=True, index=True, nullable=False)
    telefono: str = Field(nullable=False)

    usuario: Optional["Usuario"] = Relationship(back_populates="cliente")
    vehiculos: list["Vehiculo"] = Relationship(back_populates="cliente")


class Vehiculo(SQLModel, table=True):
    __tablename__ = "vehiculo"

    id: Optional[int] = Field(default=None, primary_key=True)
    cliente_id: int = Field(foreign_key="cliente.id", index=True, nullable=False)
    patente: str = Field(nullable=False)
    marca: str = Field(nullable=False)
    modelo: str = Field(nullable=False)
    anio: int = Field(nullable=False)
    borrado_en: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    __table_args__ = (
        CheckConstraint("anio BETWEEN 1950 AND 2100", name="ck_vehiculo_anio"),
        Index(
            "ix_vehiculo_patente_activa",
            "patente",
            unique=True,
            postgresql_where=text("borrado_en IS NULL"),
        ),
    )

    cliente: Optional[Cliente] = Relationship(back_populates="vehiculos")
    ordenes: list["OrdenTrabajo"] = Relationship(back_populates="vehiculo")
