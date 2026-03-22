import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.models.base import Base

class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    type = Column(String(50), nullable=False)  # e.g., 'IN', 'OUT'
    unit_price = Column(Numeric(10, 2), nullable=False, server_default='0.00')
    unit_cost = Column(Numeric(10, 2), nullable=False, server_default='0.00')
    date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Versionamento para OCC
    version = Column(Integer, default=1, nullable=False)
