from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class EstadoOrdenEnum(str, Enum):
    PENDIENTE = "PENDIENTE"
    EN_REPARACION = "EN_REPARACION"
    TERMINADA = "TERMINADA"
    CANCELADA = "CANCELADA"


class CrearItemOrdenRequest(BaseModel):
    repuesto_id: int
    cantidad: int = Field(gt=0)

    model_config = ConfigDict(extra="forbid")


class CrearOrdenRequest(BaseModel):
    vehiculo_id: int
    falla: str = Field(min_length=1)
    items: list[CrearItemOrdenRequest] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")

    @field_validator("items")
    @classmethod
    def check_no_duplicate_repuestos(
        cls, v: list[CrearItemOrdenRequest]
    ) -> list[CrearItemOrdenRequest]:
        ids = [item.repuesto_id for item in v]
        if len(ids) != len(set(ids)):
            raise ValueError("No se permiten repuestos repetidos en la orden")
        return v


class ItemOrdenDetalleResponse(BaseModel):
    repuesto_id: int
    codigo: str
    descripcion: str
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal

    model_config = ConfigDict(from_attributes=True)


class HistorialEstadoOrdenDetalleResponse(BaseModel):
    desde_estado: Optional[str] = None
    hasta_estado: str
    usuario_id: int
    cuando: datetime

    model_config = ConfigDict(from_attributes=True)


class OrdenDetalleResponse(BaseModel):
    id: int
    estado: str
    patente: str
    total: Decimal
    creada_en: datetime
    mecanico_id: Optional[int] = None
    falla: str
    cliente: str
    items: list[ItemOrdenDetalleResponse]
    historial: list[HistorialEstadoOrdenDetalleResponse]

    model_config = ConfigDict(from_attributes=True)


class OrdenListItemResponse(BaseModel):
    id: int
    estado: str
    patente: str
    total: Decimal
    creada_en: datetime
    mecanico_id: Optional[int] = None
    falla: str
    cliente: str

    model_config = ConfigDict(from_attributes=True)


class EstadoOrdenResponse(BaseModel):
    codigo: str
    descripcion: str
    posicion: int
    es_final: bool

    model_config = ConfigDict(from_attributes=True)
