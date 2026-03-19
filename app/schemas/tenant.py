from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime

class TenantBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Nome da empresa/cliente (Tenant)")
    cnpj: Optional[str] = None
    corporate_name: Optional[str] = None
    tax_regime: Optional[str] = None
    state_registration: Optional[str] = None
    certificate_a1_base64: Optional[str] = None
    certificate_password: Optional[str] = None

class TenantCreate(TenantBase):
    pass

class TenantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255, description="Nome da empresa/cliente (Tenant)")
    cnpj: Optional[str] = None
    corporate_name: Optional[str] = None
    tax_regime: Optional[str] = None
    state_registration: Optional[str] = None
    certificate_a1_base64: Optional[str] = None
    certificate_password: Optional[str] = None

class TenantResponse(TenantBase):
    id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
