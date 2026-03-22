from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID

class PackOrderItem(BaseModel):
    product_id: UUID
    quantity: int = Field(..., gt=0, description="Quantidade de caixas deste produto")

class PackOrderRequest(BaseModel):
    vehicle_id: UUID
    sales_orders_ids: Optional[List[UUID]] = Field(default=None, description="Lista de IDs de pedidos para carregar todos os itens")
    items: Optional[List[PackOrderItem]] = Field(default=None, description="Lista manual de produtos (se não usar sales_orders_ids)")
