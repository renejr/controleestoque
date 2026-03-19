from sqlalchemy import Column, String, Float, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.models.base import Base

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    license_plate = Column(String(20), nullable=False)
    model_name = Column(String(100), nullable=False)
    
    # Capacidades de Carga
    tare_weight = Column(Float, nullable=False, default=0.0) # Peso do veículo vazio (kg)
    max_weight_capacity = Column(Float, nullable=False) # Peso máximo de carga suportado (kg)
    max_volume_capacity = Column(Float, nullable=False) # Volume máximo de carga suportado (m³)
    
    # Dimensões Internas do Baú (em cm) para algoritmo de Bin Packing futuro
    compartment_width = Column(Float, nullable=False)
    compartment_height = Column(Float, nullable=False)
    compartment_length = Column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint('tenant_id', 'license_plate', name='uq_tenant_license_plate'),
    )
