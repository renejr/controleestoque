from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID

class SuggestedPurchase(BaseModel):
    product_id: UUID
    supplier_id: Optional[UUID] = None
    suggested_quantity: int = Field(..., gt=0)

class OracleRestockResponse(BaseModel):
    advice: str
    suggested_purchases: List[SuggestedPurchase] = []

class OracleInsightResponse(BaseModel):
    low_stock_count: int
    total_products: int
    healthy: bool

class OracleChatRequest(BaseModel):
    query: str

class OracleChatResponse(BaseModel):
    answer: str
