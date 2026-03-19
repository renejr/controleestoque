from pydantic import BaseModel, Field, EmailStr
from uuid import UUID
from typing import Optional

class CustomerBase(BaseModel):
    name: str = Field(..., max_length=255, description="Nome ou Razão Social do cliente")
    document: Optional[str] = Field(None, max_length=20, description="CPF ou CNPJ")
    email: Optional[EmailStr] = Field(None, description="Email de contato")
    phone: Optional[str] = Field(None, max_length=50, description="Telefone de contato")
    zip_code: Optional[str] = Field(None, max_length=20, description="CEP")
    street: Optional[str] = Field(None, max_length=255, description="Rua/Avenida")
    number: Optional[str] = Field(None, max_length=50, description="Número")
    city: Optional[str] = Field(None, max_length=100, description="Cidade")
    state: Optional[str] = Field(None, max_length=50, description="Estado (UF)")

class CustomerCreate(CustomerBase):
    pass

class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    document: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    zip_code: Optional[str] = Field(None, max_length=20)
    street: Optional[str] = Field(None, max_length=255)
    number: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)

class CustomerResponse(CustomerBase):
    id: UUID
    tenant_id: UUID

    model_config = {"from_attributes": True}
