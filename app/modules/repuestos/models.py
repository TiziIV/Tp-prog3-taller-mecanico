from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from sqlalchemy import CheckConstraint, Column, DateTime, Index, Numeric, text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.ordenes.models import OrdenTrabajo
    from app.modules.usuarios.models import Usuario


class Repuesto(SQLModel, table=True):
    __tablename__ = "repuesto"

    id: Optional[int] = Field(default=None, primary_key=True)
    codigo: str = Field(nullable=False)
    descripcion: str = Field(nullable=False)
    precio: Decimal = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
    )
    stock: int = Field(default=0, nullable=False)
    borrado_en: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    __table_args__ = (
        CheckConstraint("precio > 0", name="ck_repuesto_precio_positivo"),
        CheckConstraint("stock >= 0", name="ck_repuesto_stock_no_negativo"),
        Index(
            "ix_repuesto_codigo_activo",
            "codigo",
            unique=True,
            postgresql_where=text("borrado_en IS NULL"),
        ),
    )

    movimientos: list["MovimientoStock"] = Relationship(back_populates="repuesto")
    historial_precios: list["HistorialPrecio"] = Relationship(back_populates="repuesto")


class MovimientoStock(SQLModel, table=True):
    __tablename__ = "movimiento_stock"

    id: Optional[int] = Field(default=None, primary_key=True)
    repuesto_id: int = Field(foreign_key="repuesto.id", index=True, nullable=False)
    orden_id: Optional[int] = Field(
        default=None,
        foreign_key="orden_trabajo.id",
        index=True,
        nullable=True,
    )
    usuario_id: int = Field(foreign_key="usuario.id", index=True, nullable=False)
    cantidad: int = Field(nullable=False)
    motivo: str = Field(nullable=False)
    cuando: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))

    __table_args__ = (
        CheckConstraint("cantidad <> 0", name="ck_movimiento_stock_cantidad_no_cero"),
    )

    repuesto: Optional[Repuesto] = Relationship(back_populates="movimientos")


class HistorialPrecio(SQLModel, table=True):
    __tablename__ = "historial_precio_repuesto"

    id: Optional[int] = Field(default=None, primary_key=True)
    repuesto_id: int = Field(foreign_key="repuesto.id", index=True, nullable=False)
    usuario_id: int = Field(foreign_key="usuario.id", index=True, nullable=False)
    precio_anterior: Decimal = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
    )
    precio_nuevo: Decimal = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
    )
    cuando: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))

    __table_args__ = (
        CheckConstraint("precio_nuevo > 0", name="ck_historial_precio_nuevo_positivo"),
        CheckConstraint("precio_nuevo <> precio_anterior", name="ck_historial_precio_distinto"),
    )

    repuesto: Optional[Repuesto] = Relationship(back_populates="historial_precios")
