from typing import Optional
from uuid import UUID
from pydantic import BaseModel

class DistributionCenterBase(BaseModel):
    name: str
    address: str
    city: str
    state: str
    zip_code: str

class DistributionCenterCreate(DistributionCenterBase):
    pass

class DistributionCenterUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    version: Optional[int] = None

class DistributionCenterResponse(DistributionCenterBase):
    id: UUID
    tenant_id: UUID
    version: int

    class Config:
        from_attributes = True
