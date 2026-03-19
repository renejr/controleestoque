from pydantic import BaseModel, Field
from typing import List
from uuid import UUID

class PackOrderItem(BaseModel):
    product_id: UUID
    quantity: int = Field(..., gt=0, description="Quantidade de caixas deste produto")

class PackOrderRequest(BaseModel):
    vehicle_id: UUID
    items: List[PackOrderItem] = Field(..., min_length=1, description="Lista de produtos a serem embarcados")
