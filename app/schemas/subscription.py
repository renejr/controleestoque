from pydantic import BaseModel, Field, EmailStr
from typing import Optional

class TenantProvisionRequest(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=255, description="Nome fantasia ou Razão Social")
    document: Optional[str] = Field(None, description="CNPJ ou CPF")
    
    admin_name: str = Field(..., min_length=2, max_length=255, description="Nome do usuário administrador")
    admin_email: EmailStr = Field(..., description="E-mail que será usado para login")
    admin_password: Optional[str] = Field(None, description="Senha inicial do admin. Se não enviada, será gerada aleatoriamente")
    
    plan_type: str = Field(default="TRIAL", description="Plano assinado no gateway de pagamentos")

class TenantProvisionResponse(BaseModel):
    tenant_id: str
    admin_id: str
    company_name: str
    admin_email: str
    message: str = "Tenant provisionado com sucesso"
