from sqlalchemy import Column, String, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.models.base import Base

class TenantSetting(Base):
    __tablename__ = "tenant_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    
    company_name = Column(String(100), nullable=True)
    cnpj = Column(String(20), nullable=True)
    logo_url = Column(String(255), nullable=True)
    
    # Perfil do Oráculo
    ai_tone = Column(String(50), default="NEUTRAL", nullable=False) # CONSERVATIVE, AGGRESSIVE, NEUTRAL
