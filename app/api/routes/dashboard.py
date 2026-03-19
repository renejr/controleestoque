from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID

from app.core.deps import get_db, get_tenant_id
from app.models.product import Product
from app.models.transaction import InventoryTransaction
from app.models.ai_insight import AIInsight
from app.schemas.dashboard import DashboardSummary, LowStockAlert, RecentTransaction, AIInsightResponse
from app.services.llm_service import generate_inventory_insights
from typing import List

router = APIRouter()

@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Retorna o resumo analítico do Dashboard para o Tenant autenticado.
    Calcula total de produtos, valor total em estoque, alertas de baixo estoque e transações recentes.
    """
    
    # 1. Total de Produtos
    query_total_products = select(func.count(Product.id)).where(Product.tenant_id == tenant_id)
    result_total_products = await db.execute(query_total_products)
    total_products = result_total_products.scalar() or 0

    # 2. Valor Total do Inventário e Custo Total
    query_financials = select(
        func.sum(Product.current_stock * Product.price).label('total_value'),
        func.sum(Product.current_stock * Product.cost_price).label('total_cost')
    ).where(Product.tenant_id == tenant_id)
    
    result_financials = await db.execute(query_financials)
    row = result_financials.first()
    
    total_inventory_value = row.total_value or 0.0
    total_inventory_cost = row.total_cost or 0.0
    potential_profit = float(total_inventory_value) - float(total_inventory_cost)

    # 3. Alertas de Baixo Estoque (current_stock < 5)
    query_low_stock = (
        select(Product.id, Product.name, Product.sku, Product.current_stock)
        .where(Product.tenant_id == tenant_id, Product.current_stock < 5)
        .order_by(Product.current_stock.asc())
        .limit(10)
    )
    result_low_stock = await db.execute(query_low_stock)
    
    # Mapear os resultados para a lista de schemas esperada (dict -> schema)
    low_stock_alerts = [
        LowStockAlert(id=row.id, name=row.name, sku=row.sku, current_stock=row.current_stock)
        for row in result_low_stock
    ]

    # 4. Últimas 5 Transações (ordenadas por data DESC)
    query_recent_tx = (
        select(InventoryTransaction)
        .where(InventoryTransaction.tenant_id == tenant_id)
        .order_by(InventoryTransaction.date.desc())
        .limit(5)
    )
    result_recent_tx = await db.execute(query_recent_tx)
    recent_transactions = result_recent_tx.scalars().all()

    return DashboardSummary(
        total_products=total_products,
        total_inventory_value=float(total_inventory_value),
        total_inventory_cost=float(total_inventory_cost),
        potential_profit=float(potential_profit),
        low_stock_alerts=low_stock_alerts,
        recent_transactions=recent_transactions
    )

@router.get("/ai-insights")
async def get_ai_insights(
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Usa Inteligência Artificial (LLM) para analisar os dados do dashboard
    e fornecer 3 insights acionáveis para o negócio.
    """
    # Reutiliza a lógica de coleta de dados (poderia ser refatorada para uma função service, 
    # mas aqui chamaremos o summary logicamente para compor o prompt)
    
    # 1. Coleta dados resumidos
    summary = await get_dashboard_summary(tenant_id, db)
    
    # Busca últimas 20 transações
    query_recent_tx = (
        select(InventoryTransaction)
        .where(InventoryTransaction.tenant_id == tenant_id)
        .order_by(InventoryTransaction.date.desc())
        .limit(20)
    )
    result_recent_tx = await db.execute(query_recent_tx)
    transactions = result_recent_tx.scalars().all()
    
    # Converte o modelo Pydantic para dict para passar ao LLM
    dashboard_data = summary.model_dump()
    dashboard_data["recent_transactions"] = [
        {"product_id": str(tx.product_id), "type": tx.type, "quantity": tx.quantity, "date": str(tx.date)}
        for tx in transactions
    ]
    
    # 2. Chama o serviço de LLM
    insights = await generate_inventory_insights(dashboard_data)
    
    # 3. Salva no banco de dados com tratamento de erro robusto
    if insights and "Erro" not in insights and "IA indisponível" not in insights and "sobrecarregado" not in insights:
        try:
            db_insight = AIInsight(tenant_id=tenant_id, insight_text=insights)
            db.add(db_insight)
            await db.commit()
        except Exception as e:
            await db.rollback()
            print(f"Erro ao salvar insight no banco de dados: {e}")

    return {"insights": insights}

@router.get("/ai-insights/history", response_model=List[AIInsightResponse])
async def get_ai_insights_history(
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Retorna o histórico de análises de IA geradas para o tenant.
    """
    query = (
        select(AIInsight)
        .where(AIInsight.tenant_id == tenant_id)
        .order_by(AIInsight.created_at.desc())
    )
    result = await db.execute(query)
    return result.scalars().all()
