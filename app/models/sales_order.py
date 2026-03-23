from sqlalchemy import Column, String, Numeric, ForeignKey, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timezone

from app.models.base import Base

class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    
    # Status possíveis: DRAFT, CONFIRMED, SHIPPED, DELIVERED, CANCELLED
    status = Column(String(50), nullable=False, default="DRAFT")
    total_amount = Column(Numeric(10, 2), nullable=False, default=0.00)
    notes = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Versionamento para OCC
    version = Column(Integer, default=1, nullable=False)

    customer = relationship("Customer")
    items = relationship("SalesOrderItem", back_populates="sales_order", cascade="all, delete-orphan")
