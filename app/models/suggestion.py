from sqlalchemy import Column, String, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.models.base import Base

class Suggestion(Base):
    __tablename__ = "suggestions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    
    # Status possíveis: PENDING, IN_REVIEW, RESOLVED
    status = Column(String(50), nullable=False, default="PENDING")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
