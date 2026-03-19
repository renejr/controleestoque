from sqlalchemy import Column, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from app.models.base import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True) # Pode ser nulo se a ação for do sistema, mas idealmente vem do token
    
    action = Column(String(20), nullable=False) # 'INSERT', 'UPDATE', 'DELETE'
    table_name = Column(String(100), nullable=False, index=True)
    record_id = Column(String(100), nullable=False, index=True)
    
    old_data = Column(JSONB, nullable=True)
    new_data = Column(JSONB, nullable=True)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
