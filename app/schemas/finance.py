from pydantic import BaseModel
from typing import List
from datetime import date

class DailyFinance(BaseModel):
    date: str
    daily_revenue: float
    daily_cost: float

class FinanceSummary(BaseModel):
    realized_revenue: float
    realized_cost: float
    net_profit: float
    daily_data: List[DailyFinance]
