from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, Date, cast
from uuid import UUID
from datetime import datetime, timedelta

from app.core.deps import get_db, get_tenant_id, get_current_user
from app.models.transaction import InventoryTransaction
from app.models.user import User
from app.schemas.finance import FinanceSummary, DailyFinance

router = APIRouter()

@router.get("/summary", response_model=FinanceSummary)
async def get_finance_summary(
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Proteção RBAC: Apenas roles financeiras e gerenciais
    allowed_roles = ['ADMIN', 'MANAGER', 'FINANCIAL', 'AUDITOR']
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=403, 
            detail="Acesso Negado. Seu perfil não tem permissão para visualizar o Dashboard Financeiro."
        )

    """
    Retorna um resumo financeiro baseado nas transações de SAÍDA (OUT) dos últimos 30 dias.
    """
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # 1. Calcular Totais Globais (Receita, Custo e Lucro)
    query_totals = select(
        func.sum(InventoryTransaction.quantity * InventoryTransaction.unit_price).label('total_revenue'),
        func.sum(InventoryTransaction.quantity * InventoryTransaction.unit_cost).label('total_cost')
    ).where(
        InventoryTransaction.tenant_id == tenant_id,
        InventoryTransaction.type == 'OUT',
        InventoryTransaction.date >= thirty_days_ago
    )
    
    result_totals = await db.execute(query_totals)
    totals_row = result_totals.first()
    
    realized_revenue = float(totals_row.total_revenue or 0.0)
    realized_cost = float(totals_row.total_cost or 0.0)
    net_profit = realized_revenue - realized_cost

    # 2. Calcular Agrupamento Diário (Últimos 7 dias)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    
    # Usando cast(column, Date) nativo do SQLAlchemy
    query_daily = select(
        cast(InventoryTransaction.date, Date).label('day'),
        func.sum(InventoryTransaction.quantity * InventoryTransaction.unit_price).label('daily_revenue'),
        func.sum(InventoryTransaction.quantity * InventoryTransaction.unit_cost).label('daily_cost')
    ).where(
        InventoryTransaction.tenant_id == tenant_id,
        InventoryTransaction.type == 'OUT',
        InventoryTransaction.date >= seven_days_ago
    ).group_by(
        cast(InventoryTransaction.date, Date)
    ).order_by(
        cast(InventoryTransaction.date, Date).asc()
    )

    result_daily = await db.execute(query_daily)
    
    daily_data = []
    for row in result_daily:
        daily_data.append(
            DailyFinance(
                date=str(row.day),
                daily_revenue=float(row.daily_revenue or 0.0),
                daily_cost=float(row.daily_cost or 0.0)
            )
        )

    return FinanceSummary(
        realized_revenue=realized_revenue,
        realized_cost=realized_cost,
        net_profit=net_profit,
        daily_data=daily_data
    )