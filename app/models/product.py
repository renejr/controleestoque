import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Numeric, Integer, UniqueConstraint, Float, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.models.base import Base

class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint('tenant_id', 'sku', name='uq_tenant_sku'),
        UniqueConstraint('tenant_id', 'barcode', name='uq_tenant_barcode'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    sku = Column(String(50), nullable=False, index=True)
    barcode = Column(String(50), nullable=True, index=True)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    cost_price = Column(Numeric(10, 2), nullable=False, server_default='0.00')
    current_stock = Column(Integer, nullable=False, default=0)
    min_stock = Column(Integer, nullable=False, default=0)
    # Logística e Fiscal
    weight = Column(Float, default=0.0) # Peso em Kg
    width = Column(Float, default=0.0) # Largura em cm
    height = Column(Float, default=0.0) # Altura em cm
    length = Column(Float, default=0.0) # Comprimento em cm
    
    ncm = Column(String(10), nullable=True) # Nomenclatura Comum do Mercosul
    cfop = Column(String(4), nullable=True) # Código Fiscal de Operações e Prestações
    cest = Column(String(7), nullable=True) # Código Especificador da Substituição Tributária
    origin = Column(String(1), default="0") # Origem da mercadoria (0 - Nacional, 1 - Estrangeira, etc)
    
    # Vinculo com Centro de Distribuição
    cd_id = Column(UUID(as_uuid=True), ForeignKey('distribution_centers.id', ondelete="SET NULL"), nullable=True)

    # Embedding para Busca Semântica (Requer extensão pgvector)
    embedding = Column(Vector(384), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Versionamento para Controle de Concorrência Otimista (OCC)
    version = Column(Integer, default=1, nullable=False)
