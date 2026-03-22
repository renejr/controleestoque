from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal

class ProductBase(BaseModel):
    sku: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    barcode: Optional[str] = None
    description: Optional[str] = None
    price: Decimal = Field(..., ge=0)
    cost_price: Decimal = Field(0, ge=0)
    current_stock: int = Field(0, ge=0)
    min_stock: int = Field(0, ge=0)
    weight: Optional[float] = Field(None, ge=0)
    width: Optional[float] = Field(None, ge=0)
    height: Optional[float] = Field(None, ge=0)
    length: Optional[float] = Field(None, ge=0)
    ncm: Optional[str] = Field(None, max_length=8)
    cfop: Optional[str] = Field(None, max_length=4)
    cest: Optional[str] = Field(None, max_length=7)
    origin: Optional[int] = Field(0, ge=0)
    embedding: Optional[List[float]] = Field(None, max_length=384, min_length=384)
    cd_id: Optional[UUID] = None

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    cost_price: Optional[Decimal] = Field(None, ge=0)
    current_stock: Optional[int] = Field(None, ge=0)
    min_stock: Optional[int] = Field(None, ge=0)
    weight: Optional[float] = Field(None, ge=0)
    width: Optional[float] = Field(None, ge=0)
    height: Optional[float] = Field(None, ge=0)
    length: Optional[float] = Field(None, ge=0)
    ncm: Optional[str] = Field(None, max_length=8)
    cfop: Optional[str] = Field(None, max_length=4)
    cest: Optional[str] = Field(None, max_length=7)
    origin: Optional[int] = Field(None, ge=0)
    embedding: Optional[List[float]] = Field(None, max_length=384, min_length=384)
    cd_id: Optional[UUID] = None
    version: Optional[int] = None

class ProductResponse(ProductBase):
    id: UUID
    tenant_id: UUID
    created_at: datetime
    profit_margin: Optional[float] = None
    version: int

    model_config = {"from_attributes": True}
    
    @model_validator(mode='after')
    def calculate_profit_margin(self):
        if self.price and self.price > 0 and self.cost_price is not None:
            self.profit_margin = float(((self.price - self.cost_price) / self.price) * 100)
        else:
            self.profit_margin = 0.0
        return self
