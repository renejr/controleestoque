from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID

class SupplierBase(BaseModel):
    name: str
    cnpj: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    contact_name: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None

class SupplierCreate(SupplierBase):
    pass

class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    cnpj: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    contact_name: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None

class SupplierResponse(SupplierBase):
    id: UUID
    tenant_id: UUID

    model_config = {"from_attributes": True}
