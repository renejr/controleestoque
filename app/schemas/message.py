from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

class ChatMessageBase(BaseModel):
    receiver_id: UUID
    content: str

class ChatMessageCreate(ChatMessageBase):
    pass

class ChatMessageResponse(ChatMessageBase):
    id: UUID
    tenant_id: UUID
    sender_id: UUID
    is_read: bool
    created_at: datetime
    
    sender_name: Optional[str] = None
    receiver_name: Optional[str] = None

    class Config:
        from_attributes = True
