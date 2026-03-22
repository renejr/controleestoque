from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional

class VehicleBase(BaseModel):
    license_plate: str = Field(..., max_length=20, description="Placa do veículo")
    model_name: str = Field(..., max_length=100, description="Modelo do veículo")
    tare_weight: float = Field(0.0, ge=0, description="Tara do veículo em kg")
    max_weight_capacity: float = Field(..., gt=0, description="Capacidade máxima de peso em kg")
    max_volume_capacity: float = Field(..., gt=0, description="Capacidade máxima de volume em m³")
    compartment_width: float = Field(..., gt=0, description="Largura do baú em cm")
    compartment_height: float = Field(..., gt=0, description="Altura do baú em cm")
    compartment_length: float = Field(..., gt=0, description="Profundidade do baú em cm")
    cd_id: Optional[UUID] = Field(None, description="ID do Centro de Distribuição (Base)")

class VehicleCreate(VehicleBase):
    pass

class VehicleUpdate(BaseModel):
    license_plate: Optional[str] = Field(None, max_length=20)
    model_name: Optional[str] = Field(None, max_length=100)
    tare_weight: Optional[float] = Field(None, ge=0)
    max_weight_capacity: Optional[float] = Field(None, gt=0)
    max_volume_capacity: Optional[float] = Field(None, gt=0)
    compartment_width: Optional[float] = Field(None, gt=0)
    compartment_height: Optional[float] = Field(None, gt=0)
    compartment_length: Optional[float] = Field(None, gt=0)
    cd_id: Optional[UUID] = Field(None)

class VehicleResponse(VehicleBase):
    id: UUID
    tenant_id: UUID

    model_config = {"from_attributes": True}
