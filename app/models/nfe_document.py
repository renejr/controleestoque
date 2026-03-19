import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.models.base import Base

class NfeDocument(Base):
    __tablename__ = "nfe_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    sales_order_id = Column(UUID(as_uuid=True), ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Status possíveis: GENERATING, AUTHORIZED, REJECTED, CANCELLED
    status = Column(String(50), nullable=False, default="GENERATING")
    
    access_key = Column(String(44), nullable=True)
    protocol_number = Column(String(50), nullable=True)
    
    xml_content = Column(Text, nullable=True)
    pdf_url = Column(String(255), nullable=True) # ou danfe_base64
    sefaz_message = Column(String(500), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
