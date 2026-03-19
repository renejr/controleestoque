from sqlalchemy import Column, String, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.models.base import Base

class Customer(Base):
    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String(255), nullable=False)
    document = Column(String(20), nullable=True) # CPF ou CNPJ
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    
    # Dados de Roteirização/Logística
    zip_code = Column(String(20), nullable=True)
    street = Column(String(255), nullable=True)
    number = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)

    __table_args__ = (
        UniqueConstraint('tenant_id', 'document', name='uq_tenant_customer_document'),
    )
