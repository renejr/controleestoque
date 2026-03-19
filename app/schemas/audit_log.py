from pydantic import BaseModel
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime

class AuditLogResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: Optional[UUID] = None
    action: str
    table_name: str
    record_id: str
    old_data: Optional[Dict[str, Any]] = None
    new_data: Optional[Dict[str, Any]] = None
    timestamp: datetime

    model_config = {"from_attributes": True}

class SuperAdminAuditLogResponse(AuditLogResponse):
    tenant_name: str
