from sqlalchemy import Column, String, ForeignKey, Text, DateTime, Numeric, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.models.base import Base

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False)
    
    order_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(String(20), nullable=False, default="DRAFT") # DRAFT, PENDING, RECEIVED, COMPLETED, CANCELLED
    total_amount = Column(Numeric(10, 2), nullable=False, default=0.00)
    notes = Column(Text, nullable=True)
    
    cd_id = Column(UUID(as_uuid=True), ForeignKey('distribution_centers.id', ondelete="RESTRICT"), nullable=True)
    version = Column(Integer, default=1, nullable=False)

    # Relacionamentos
    supplier = relationship("Supplier", back_populates="purchase_orders")
    distribution_center = relationship("DistributionCenter")
    items = relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")
