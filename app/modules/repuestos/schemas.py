from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class CrearRepuestoRequest(BaseModel):
    codigo: str = Field(min_length=1)
    descripcion: str = Field(min_length=1)
    precio: Decimal = Field(gt=0)
    stock_inicial: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class ActualizarRepuestoRequest(BaseModel):
    descripcion: Optional[str] = Field(default=None, min_length=1)
    precio: Optional[Decimal] = Field(default=None, gt=0)

    model_config = ConfigDict(extra="forbid")


class ReponerRepuestoRequest(BaseModel):
    cantidad: int = Field(gt=0)
    motivo: str = Field(default="Reposición de stock", min_length=1)

    model_config = ConfigDict(extra="forbid")


class RepuestoResponse(BaseModel):
    id: int
    codigo: str
    descripcion: str
    precio: Decimal
    stock: int

    model_config = ConfigDict(from_attributes=True)


class MovimientoStockResponse(BaseModel):
    id: int
    repuesto_id: int
    orden_id: Optional[int] = None
    usuario_id: int
    cantidad: int
    motivo: str
    cuando: datetime

    model_config = ConfigDict(from_attributes=True)


class HistorialPrecioResponse(BaseModel):
    id: int
    repuesto_id: int
    usuario_id: int
    precio_anterior: Decimal
    precio_nuevo: Decimal
    cuando: datetime

    model_config = ConfigDict(from_attributes=True)
