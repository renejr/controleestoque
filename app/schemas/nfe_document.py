from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime

class NfeDocumentBase(BaseModel):
    sales_order_id: UUID
    status: str = Field(default="GENERATING", description="GENERATING, AUTHORIZED, REJECTED, CANCELLED")
    access_key: Optional[str] = None
    protocol_number: Optional[str] = None
    xml_content: Optional[str] = None
    pdf_url: Optional[str] = None
    sefaz_message: Optional[str] = None

class NfeDocumentCreate(NfeDocumentBase):
    pass

class NfeDocumentUpdate(BaseModel):
    status: Optional[str] = None
    access_key: Optional[str] = None
    protocol_number: Optional[str] = None
    xml_content: Optional[str] = None
    pdf_url: Optional[str] = None
    sefaz_message: Optional[str] = None

class NfeDocumentResponse(NfeDocumentBase):
    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
