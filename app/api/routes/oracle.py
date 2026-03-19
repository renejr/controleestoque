from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.deps import get_db, get_tenant_id
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.schemas.oracle import OracleRestockResponse
from app.services.llm_service import generate_restock_advice

router = APIRouter()

@router.get("/restock-advice", response_model=OracleRestockResponse)
async def get_restock_advice(
    tenant_id: UUID = Depends(get_tenant_id),
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
