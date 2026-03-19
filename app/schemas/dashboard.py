from pydantic import BaseModel
from typing import List
from uuid import UUID
from datetime import datetime

class LowStockAlert(BaseModel):
    id: UUID
    name: str
    sku: str
    current_stock: int

    model_config = {"from_attributes": True}

class RecentTransaction(BaseModel):
    id: UUID
    product_id: UUID
    type: str
    quantity: int
    unit_price: float
    unit_cost: float
    date: datetime

    model_config = {"from_attributes": True}

class DashboardSummary(BaseModel):
    total_products: int
    total_inventory_value: float
    total_inventory_cost: float
    potential_profit: float
    low_stock_alerts: List[LowStockAlert]
    recent_transactions: List[RecentTransaction]

class AIInsightResponse(BaseModel):
    id: UUID
    insight_text: str
    created_at: datetime

    model_config = {"from_attributes": True}
