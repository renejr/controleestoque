from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.models.base import Base

class CollectionOrder(Base):
    __tablename__ = "collection_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    sender_name = Column(String(255), nullable=False)
    
    # Endereço detalhado
    street = Column(String(255), nullable=False, default="")
    number = Column(String(50), nullable=False, default="")
    city = Column(String(100), nullable=False, default="")
    state = Column(String(50), nullable=False, default="")
    zip_code = Column(String(20), nullable=False, default="")
    
    # Mantendo pickup_address por compatibilidade temporária (pode ser o compilado)
    pickup_address = Column(String(500), nullable=False)
    
    scheduled_date = Column(DateTime(timezone=True), nullable=False)
    
    total_volumes = Column(Integer, nullable=False, default=1)
    total_weight = Column(Float, nullable=False, default=0.0)
    
    # Relações operacionais
    distribution_center_id = Column(UUID(as_uuid=True), ForeignKey("distribution_centers.id", ondelete="SET NULL"), nullable=True)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True)
    
    status = Column(String(50), nullable=False, default="PENDING") # PENDING, ROUTED, IN_TRANSIT, COLLECTED, CANCELED

    # Relacionamentos (opcional para joins)
    distribution_center = relationship("DistributionCenter")
    vehicle = relationship("Vehicle")
