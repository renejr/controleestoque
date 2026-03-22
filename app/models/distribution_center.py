from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.models.base import Base

class DistributionCenter(Base):
    __tablename__ = "distribution_centers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(2), nullable=False)
    zip_code = Column(String(20), nullable=False)
