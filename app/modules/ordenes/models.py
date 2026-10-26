from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.clientes.models import Vehiculo
    from app.modules.repuestos.models import Repuesto
    from app.modules.usuarios.models import Usuario


class EstadoOrden(SQLModel, table=True):
    __tablename__ = "estado_orden"

    codigo: str = Field(
        sa_column=Column(String, primary_key=True),
    )
    descripcion: str = Field(nullable=False)
    posicion: int = Field(unique=True, index=True, nullable=False)
    es_final: bool = Field(default=False, nullable=False)


class OrdenTrabajo(SQLModel, table=True):
    __tablename__ = "orden_trabajo"

    id: Optional[int] = Field(default=None, primary_key=True)
    vehiculo_id: int = Field(foreign_key="vehiculo.id", index=True, nullable=False)
    mecanico_id: Optional[int] = Field(
        default=None,
        foreign_key="usuario.id",
        index=True,
        nullable=True,
    )
    estado: str = Field(foreign_key="estado_orden.codigo", index=True, nullable=False)
    falla: str = Field(nullable=False)
    creada_en: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    total: Decimal = Field(
        sa_column=Column(Numeric(12, 2), nullable=False),
    )

    __table_args__ = (
        CheckConstraint("total >= 0", name="ck_orden_trabajo_total_no_negativo"),
    )

    vehiculo: Optional["Vehiculo"] = Relationship(back_populates="ordenes")
    items: list["ItemOrden"] = Relationship(back_populates="orden")
    historial: list["HistorialEstadoOrden"] = Relationship(back_populates="orden")
    estado_rel: Optional[EstadoOrden] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[OrdenTrabajo.estado]"},
    )
    mecanico: Optional["Usuario"] = Relationship()


class ItemOrden(SQLModel, table=True):
    __tablename__ = "item_orden"

    id: Optional[int] = Field(default=None, primary_key=True)
    orden_id: int = Field(foreign_key="orden_trabajo.id", index=True, nullable=False)
    repuesto_id: int = Field(foreign_key="repuesto.id", index=True, nullable=False)
    cantidad: int = Field(nullable=False)
    precio_unitario: Decimal = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
    )

    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_item_orden_cantidad_positiva"),
        CheckConstraint("precio_unitario > 0", name="ck_item_orden_precio_positivo"),
        UniqueConstraint("orden_id", "repuesto_id", name="uq_item_orden_orden_repuesto"),
    )

    orden: Optional[OrdenTrabajo] = Relationship(back_populates="items")
    repuesto: Optional["Repuesto"] = Relationship()


class HistorialEstadoOrden(SQLModel, table=True):
    __tablename__ = "historial_estado_orden"

    id: Optional[int] = Field(default=None, primary_key=True)
    orden_id: int = Field(foreign_key="orden_trabajo.id", index=True, nullable=False)
    desde_estado: Optional[str] = Field(
        default=None,
        foreign_key="estado_orden.codigo",
        index=True,
        nullable=True,
    )
    hasta_estado: str = Field(
        foreign_key="estado_orden.codigo",
        index=True,
        nullable=False,
    )
    usuario_id: int = Field(foreign_key="usuario.id", index=True, nullable=False)
    cuando: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    orden: Optional[OrdenTrabajo] = Relationship(back_populates="historial")
    desde_estado_rel: Optional[EstadoOrden] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[HistorialEstadoOrden.desde_estado]"},
    )
    hasta_estado_rel: Optional[EstadoOrden] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[HistorialEstadoOrden.hasta_estado]"},
    )
    usuario: Optional["Usuario"] = Relationship()
