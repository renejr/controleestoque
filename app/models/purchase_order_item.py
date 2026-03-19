from sqlalchemy import Column, ForeignKey, Numeric, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.models.base import Base

class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purchase_order_id = Column(UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    
    quantity = Column(Float, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)

    # Relacionamentos
    purchase_order = relationship("PurchaseOrder", back_populates="items")
    product = relationship("Product")
