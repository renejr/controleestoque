from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.models.base import Base

class CollectionOrderItem(Base):
    __tablename__ = "collection_order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    collection_order_id = Column(UUID(as_uuid=True), ForeignKey("collection_orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    
    quantity = Column(Integer, nullable=False, default=1)

    # Relacionamentos
    collection_order = relationship("CollectionOrder", back_populates="items")
    product = relationship("Product")