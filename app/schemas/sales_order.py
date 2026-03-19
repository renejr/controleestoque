from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime

class SalesOrderItemBase(BaseModel):
    product_id: UUID
    quantity: int = Field(..., gt=0, description="Quantidade de produtos vendidos")
    unit_price: float = Field(..., ge=0, description="Preço de venda unitário no momento do pedido")

class SalesOrderItemCreate(SalesOrderItemBase):
    pass

class SalesOrderItemResponse(SalesOrderItemBase):
    id: UUID
    sales_order_id: UUID

    model_config = {"from_attributes": True}


class SalesOrderBase(BaseModel):
    customer_id: UUID
    notes: Optional[str] = Field(None, description="Observações gerais do pedido")

class SalesOrderCreate(SalesOrderBase):
    items: List[SalesOrderItemCreate] = Field(..., min_length=1, description="Itens do pedido de venda")

class SalesOrderStatusUpdate(BaseModel):
    status: str = Field(..., description="Novo status do pedido (ex: CONFIRMED, SHIPPED, DELIVERED, CANCELLED)")

class SalesOrderResponse(SalesOrderBase):
    id: UUID
    tenant_id: UUID
    status: str
    total_amount: float
    created_at: datetime
    items: List[SalesOrderItemResponse] = []

    model_config = {"from_attributes": True}
