import uuid
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.models.base import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    cnpj = Column(String(14), unique=True, index=True, nullable=True)
    corporate_name = Column(String(255), nullable=True)
    tax_regime = Column(String(50), nullable=True) # 'Simples Nacional', 'Lucro Presumido', 'Lucro Real'
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
