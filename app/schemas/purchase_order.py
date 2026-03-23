from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal

# --- Items ---
class PurchaseOrderItemBase(BaseModel):
    product_id: UUID
    quantity: float = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)

class PurchaseOrderItemCreate(PurchaseOrderItemBase):
    pass

class PurchaseOrderItemResponse(PurchaseOrderItemBase):
    id: UUID
    purchase_order_id: UUID

    model_config = {"from_attributes": True}

# --- Order ---
class PurchaseOrderBase(BaseModel):
    supplier_id: UUID
    cd_id: Optional[UUID] = None
    status: str = Field(default="DRAFT", pattern="^(DRAFT|PENDING|RECEIVED|COMPLETED|CANCELLED)$")
    total_amount: Decimal = Field(default=0.00, ge=0)
    notes: Optional[str] = None

class PurchaseOrderCreate(PurchaseOrderBase):
    items: List[PurchaseOrderItemCreate] = []

class PurchaseOrderUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(DRAFT|PENDING|RECEIVED|COMPLETED|CANCELLED)$")
    total_amount: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None
    cd_id: Optional[UUID] = None
    version: Optional[int] = None

class PurchaseOrderResponse(PurchaseOrderBase):
    id: UUID
    tenant_id: UUID
    order_date: datetime
    version: int
    items: List[PurchaseOrderItemResponse] = []

    model_config = {"from_attributes": True}
