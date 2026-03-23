from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, Date, cast
from uuid import UUID
from datetime import datetime, timedelta, date
import httpx

from app.core.deps import get_db, get_tenant_id, get_current_user
from app.core.config import settings
from app.models.transaction import InventoryTransaction
from app.models.tenant_setting import TenantSetting
from app.models.product import Product
from app.models.distribution_center import DistributionCenter
from app.models.user import User
from app.schemas.finance import FinanceSummary, DailyFinance

router = APIRouter()

@router.get("/summary", response_model=FinanceSummary)
async def get_finance_summary(
    start_date: date = Query(None, description="Data inicial para o gráfico diário"),
    end_date: date = Query(None, description="Data final para o gráfico diário"),
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
    Retorna um resumo financeiro baseado nas transações de SAÍDA (OUT) dos últimos 30 dias (totais)
    e um agrupamento diário customizável para o gráfico.
    """
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # 1. Calcular Totais Globais (Receita, Custo e Lucro) - Mantemos 30 dias para os cards de KPI
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

    # 2. Calcular Agrupamento Diário (Range customizado)
    # Se não informar datas, default é últimos 7 dias até hoje
    if not end_date:
        end_date = datetime.utcnow().date()
    if not start_date:
        start_date = end_date - timedelta(days=7)
        
    # Converter para datetime para comparação correta
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Usando cast(column, Date) nativo do SQLAlchemy
    query_daily = select(
        cast(InventoryTransaction.date, Date).label('day'),
        func.sum(InventoryTransaction.quantity * InventoryTransaction.unit_price).label('daily_revenue'),
        func.sum(InventoryTransaction.quantity * InventoryTransaction.unit_cost).label('daily_cost')
    ).where(
        InventoryTransaction.tenant_id == tenant_id,
        InventoryTransaction.type == 'OUT',
        InventoryTransaction.date >= start_datetime,
        InventoryTransaction.date <= end_datetime
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

@router.get("/insights")
async def get_finance_insights(
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Proteção RBAC: Apenas roles financeiras e gerenciais
    allowed_roles = ['ADMIN', 'MANAGER', 'FINANCIAL', 'AUDITOR']
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=403, 
            detail="Acesso Negado. Seu perfil não tem permissão para visualizar Insights Financeiros."
        )

    # 1. Calcular Totais do Mês Atual para o Oráculo
    first_day_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    query_totals = select(
        func.sum(InventoryTransaction.quantity * InventoryTransaction.unit_price).label('total_revenue'),
        func.sum(InventoryTransaction.quantity * InventoryTransaction.unit_cost).label('total_cost')
    ).where(
        InventoryTransaction.tenant_id == tenant_id,
        InventoryTransaction.type == 'OUT',
        InventoryTransaction.date >= first_day_of_month
    )
    
    result_totals = await db.execute(query_totals)
    totals_row = result_totals.first()
    
    revenue = float(totals_row.total_revenue or 0.0)
    cost = float(totals_row.total_cost or 0.0)
    profit = revenue - cost
    margin = (profit / revenue * 100) if revenue > 0 else 0.0

    # 2. Busca o Perfil do Oráculo nas Configurações do Tenant
    query_settings = select(TenantSetting).where(TenantSetting.tenant_id == tenant_id)
    result_settings = await db.execute(query_settings)
    settings = result_settings.scalars().first()
    ai_tone = settings.ai_tone if settings else "NEUTRAL"

    tone_instructions = {
        "CONSERVATIVE": "Seja extremamente conservador, priorize o corte de custos e proteção de caixa antes de qualquer expansão.",
        "AGGRESSIVE": "Seja arrojado, sugira reinvestir lucros agressivamente em marketing, compras em volume para baixar CMV e expansão de mercado.",
        "NEUTRAL": "Seja equilibrado, analise de forma técnica e sugira otimizações moderadas de processo."
    }
    
    selected_tone_instruction = tone_instructions.get(ai_tone, tone_instructions["NEUTRAL"])

    # 3. Construir o Prompt para o Ollama
    system_prompt = (
        "Você é o CFO (Diretor Financeiro) de uma empresa de varejo. "
        f"{selected_tone_instruction} "
        "Analise os indicadores financeiros do mês atual e forneça um insight "
        "direto, executivo e acionável. Seja extremamente conciso, use no máximo 2 frases. "
        "Não cumprimente, vá direto ao ponto."
    )
    
    user_prompt = (
        f"Resultados do mês: Faturamento R$ {revenue:.2f}, "
        f"CMV (Custo) R$ {cost:.2f}, "
        f"Lucro Bruto R$ {profit:.2f}, "
        f"Margem de Lucro {margin:.1f}%."
    )

    # 4. Chamar o Ollama Local
    try:
        from app.core.config import settings as app_settings
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{app_settings.OLLAMA_URL}/api/generate",
                json={
                    "model": "llama3.2:1b",
                    "system": system_prompt,
                    "prompt": user_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3 # Mais determinístico/analítico
                    }
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                insight_text = data.get("response", "").strip()
                return {"insight": insight_text}
            else:
                return {"insight": "O Oráculo Financeiro está temporariamente indisponível."}
    except Exception as e:
        return {"insight": f"Não foi possível conectar ao motor de IA. Detalhe: {str(e)}"}

@router.get("/valuation-by-cd")
async def get_valuation_by_cd(
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retorna o valor total de inventário (current_stock * cost_price) 
    agrupado por Centro de Distribuição.
    """
    # Proteção RBAC: Apenas roles financeiras e gerenciais
    allowed_roles = ['ADMIN', 'MANAGER', 'FINANCIAL']
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=403, 
            detail="Acesso Negado. Seu perfil não tem permissão para visualizar a Valorização por CD."
        )

    # Agrupar por CD, usando LEFT OUTER JOIN para não perder os órfãos
    query = select(
        DistributionCenter.name.label('cd_name'),
        func.sum(Product.current_stock).label('total_items'),
        func.sum(Product.current_stock * Product.cost_price).label('total_value')
    ).outerjoin(
        DistributionCenter, Product.cd_id == DistributionCenter.id
    ).where(
        Product.tenant_id == tenant_id
    ).group_by(
        DistributionCenter.name
    )

    result = await db.execute(query)
    
    valuation_data = []
    for row in result:
        cd_name = row.cd_name if row.cd_name else "Sem CD Vinculado (Órfãos)"
        valuation_data.append({
            "cd_name": cd_name,
            "total_items": int(row.total_items or 0),
            "total_value": float(row.total_value or 0.0)
        })

    # Ordena pelo maior valor primeiro
    valuation_data.sort(key=lambda x: x['total_value'], reverse=True)

    return valuation_data