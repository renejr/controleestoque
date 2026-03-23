from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID

from app.core.deps import get_db, get_tenant_id, get_current_user
from app.models.product import Product
from app.models.user import User
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.schemas.oracle import OracleRestockResponse, OracleInsightResponse, OracleChatRequest, OracleChatResponse
from app.services.llm_service import generate_restock_advice, generate_cso_chat_answer

router = APIRouter()

@router.get("/insights", response_model=OracleInsightResponse)
async def get_oracle_insights(
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retorna métricas rápidas do banco de dados para popular os cards do CSO.
    """
    # Total de produtos
    query_total = select(func.count(Product.id)).where(Product.tenant_id == tenant_id)
    total_result = await db.execute(query_total)
    total_products = total_result.scalar_one_or_none() or 0

    # Produtos com estoque baixo
    query_low = select(func.count(Product.id)).where(
        Product.tenant_id == tenant_id,
        Product.current_stock <= Product.min_stock
    )
    low_result = await db.execute(query_low)
    low_stock_count = low_result.scalar_one_or_none() or 0

    healthy = low_stock_count == 0

    return OracleInsightResponse(
        low_stock_count=low_stock_count,
        total_products=total_products,
        healthy=healthy
    )

@router.post("/chat", response_model=OracleChatResponse)
async def chat_with_cso(
    request: OracleChatRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Recebe uma pergunta do usuário, busca o contexto atual do estoque 
    e envia para o LLM responder.
    """
    # 1. Monta um resumo do estoque para servir de contexto
    query = select(Product).where(Product.tenant_id == tenant_id).limit(50) # Limitamos a 50 para não estourar o token limit do LLM
    result = await db.execute(query)
    products = result.scalars().all()
    
    if not products:
        context_str = "O estoque está completamente vazio. Não há produtos cadastrados."
    else:
        context_lines = []
        for p in products:
            status = "CRÍTICO" if p.current_stock <= p.min_stock else "OK"
            context_lines.append(f"- {p.name} (SKU: {p.sku}): Estoque Atual: {p.current_stock} | Mínimo: {p.min_stock} | Status: {status} | Custo: R${p.cost_price}")
        context_str = "\n".join(context_lines)

    # 2. Envia para o Ollama
    answer = await generate_cso_chat_answer(request.query, context_str)
    
    return OracleChatResponse(answer=answer)

@router.get("/restock-advice", response_model=OracleRestockResponse)
async def get_restock_advice(
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Aciona o LLM local para analisar produtos com estoque abaixo do mínimo e gerar um plano de compras.
    """
    
    # 1. Busca produtos críticos do tenant
    query = select(Product).where(
        Product.tenant_id == tenant_id,
        Product.current_stock <= Product.min_stock
    )
    result = await db.execute(query)
    critical_products = result.scalars().all()
    
    if not critical_products:
        return OracleRestockResponse(
            advice="Estoque saudável! Nenhum produto está abaixo da quantidade mínima exigida no momento.",
            suggested_purchases=[]
        )
        
    # 2. Monta o contexto para a IA
    # Vamos tentar descobrir o último fornecedor que vendeu esse produto para facilitar a vida da IA
    context_data = []
    for p in critical_products:
        # Tenta achar o último fornecedor via Ordens de Compra concluídas
        last_supplier_query = (
            select(PurchaseOrder.supplier_id)
            .join(PurchaseOrderItem, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id)
            .where(PurchaseOrderItem.product_id == p.id, PurchaseOrder.status == "COMPLETED")
            .order_by(PurchaseOrder.order_date.desc())
            .limit(1)
        )
        supplier_result = await db.execute(last_supplier_query)
        last_supplier_id = supplier_result.scalar_one_or_none()
        
        context_data.append({
            "id": str(p.id),
            "name": p.name,
            "current_stock": p.current_stock,
            "min_stock": p.min_stock,
            "cost_price": float(p.cost_price),
            "supplier_id": str(last_supplier_id) if last_supplier_id else None,
            "supplier_name": "Último Fornecedor Conhecido" if last_supplier_id else "Desconhecido"
        })
        
    # 3. Chama o serviço do Ollama
    try:
        advice_json = await generate_restock_advice(context_data)
        
        # O FastAPI + Pydantic vai validar e limpar o JSON gerado automaticamente
        return OracleRestockResponse(**advice_json)
        
    except Exception as e:
        # Se for erro de conexão com Ollama, retorna 503
        if "offline" in str(e).lower() or "timeout" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
