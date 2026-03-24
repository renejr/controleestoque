from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional

class CollectionOrderBase(BaseModel):
    sender_name: str = Field(..., description="Nome do remetente (fornecedor/cliente)")
    
    street: str = Field(..., description="Rua do endereço")
    number: str = Field(..., description="Número do endereço")
    city: str = Field(..., description="Cidade")
    state: str = Field(..., description="Estado")
    zip_code: str = Field(..., description="CEP")
    
    pickup_address: str = Field(..., description="Endereço de coleta compilado")
    
    scheduled_date: datetime = Field(..., description="Data agendada para a coleta")
    total_volumes: int = Field(1, ge=1, description="Quantidade total de volumes")
    total_weight: float = Field(0.0, ge=0, description="Peso total estimado em kg")
    
    distribution_center_id: Optional[UUID] = Field(None, description="ID do CD de destino")
    vehicle_id: Optional[UUID] = Field(None, description="ID do Veículo escalado")
    
    status: str = Field("PENDING", description="Status da coleta (PENDING, ROUTED, IN_TRANSIT, COLLECTED, CANCELED)")

class CollectionOrderCreate(CollectionOrderBase):
    pass

class CollectionOrderUpdate(BaseModel):
    sender_name: Optional[str] = None
    street: Optional[str] = None
    number: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    pickup_address: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    total_volumes: Optional[int] = None
    total_weight: Optional[float] = None
    distribution_center_id: Optional[UUID] = None
    vehicle_id: Optional[UUID] = None
    status: Optional[str] = None

class CollectionOrderStatusUpdate(BaseModel):
    status: str = Field(..., description="Novo status da coleta (ex: COLLECTED)")

class CollectionOrderResponse(CollectionOrderBase):
    id: UUID
    tenant_id: UUID

    model_config = {"from_attributes": True}
