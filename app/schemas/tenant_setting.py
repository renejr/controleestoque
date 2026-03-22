from typing import Optional
from uuid import UUID
from pydantic import BaseModel

class TenantSettingBase(BaseModel):
    company_name: Optional[str] = None
    cnpj: Optional[str] = None
    logo_url: Optional[str] = None
    ai_tone: str = "NEUTRAL" # CONSERVATIVE, AGGRESSIVE, NEUTRAL

class TenantSettingUpdate(TenantSettingBase):
    pass

class TenantSettingResponse(TenantSettingBase):
    id: UUID
    tenant_id: UUID

    class Config:
        from_attributes = True
