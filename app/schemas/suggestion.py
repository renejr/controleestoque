from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

class SuggestionBase(BaseModel):
    title: str
    description: str

class SuggestionCreate(SuggestionBase):
    pass

class SuggestionUpdate(BaseModel):
    status: Optional[str] = Field(None, description="PENDING, IN_REVIEW, RESOLVED")

class SuggestionResponse(SuggestionBase):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
