from pydantic import BaseModel, Field
from typing import Literal
from uuid import UUID
from datetime import datetime
from decimal import Decimal

class TransactionBase(BaseModel):
    product_id: UUID
    quantity: int = Field(..., gt=0, description="Quantidade da movimentação (deve ser maior que zero)")
    type: Literal['IN', 'OUT'] = Field(..., description="Tipo de movimentação: 'IN' (Entrada) ou 'OUT' (Saída)")

class TransactionCreate(TransactionBase):
    pass

class TransactionResponse(TransactionBase):
    id: UUID
    tenant_id: UUID
    unit_price: Decimal
    unit_cost: Decimal
    date: datetime

    model_config = {"from_attributes": True}
