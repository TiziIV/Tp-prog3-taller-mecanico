from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class CrearClienteRequest(BaseModel):
    nombre: str = Field(min_length=1)
    documento: str = Field(min_length=1)
    telefono: str = Field(min_length=1)
    usuario_id: Optional[int] = None

    model_config = ConfigDict(extra="forbid")


class CrearVehiculoRequest(BaseModel):
    patente: str = Field(min_length=1)
    marca: str = Field(min_length=1)
    modelo: str = Field(min_length=1)
    anio: int = Field(ge=1950, le=2100)

    model_config = ConfigDict(extra="forbid")


class VehiculoResponse(BaseModel):
    id: int
    cliente_id: int
    patente: str
    marca: str
    modelo: str
    anio: int
    borrado_en: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ClienteResponse(BaseModel):
    id: int
    usuario_id: Optional[int] = None
    nombre: str
    documento: str
    telefono: str

    model_config = ConfigDict(from_attributes=True)


class ClienteDetalleResponse(BaseModel):
    id: int
    usuario_id: Optional[int] = None
    nombre: str
    documento: str
    telefono: str
    vehiculos: list[VehiculoResponse] = []

    model_config = ConfigDict(from_attributes=True)
