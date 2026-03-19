from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from uuid import UUID

from app.core.deps import get_db, get_tenant_id, get_current_user
from app.models.sales_order import SalesOrder
from app.models.sales_order_item import SalesOrderItem
from app.models.product import Product
from app.models.customer import Customer
from app.models.transaction import InventoryTransaction
from app.schemas.sales_order import SalesOrderCreate, SalesOrderResponse, SalesOrderStatusUpdate
from app.services.audit_service import log_audit_event

router = APIRouter()

@router.post("/", response_model=SalesOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_sales_order(
    order_in: SalesOrderCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    # Verifica se o cliente existe
    query_customer = select(Customer).where(Customer.id == order_in.customer_id, Customer.tenant_id == tenant_id)
    customer = (await db.execute(query_customer)).scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")

    # Cria o cabeçalho do pedido
    order = SalesOrder(
        tenant_id=tenant_id,
        customer_id=order_in.customer_id,
        status="DRAFT",
        notes=order_in.notes,
        total_amount=0.0
    )
    db.add(order)
    await db.flush() # Para gerar o order.id
    
    total_amount = 0.0
    
    # Processa os itens e calcula o total
    for item_in in order_in.items:
        # Verifica o produto
        query_prod = select(Product).where(Product.id == item_in.product_id, Product.tenant_id == tenant_id)
        product = (await db.execute(query_prod)).scalars().first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Produto com ID {item_in.product_id} não encontrado.")
            
        # Opcional: verificar se há estoque suficiente já no momento da criação (depende da regra de negócio)
        # Por enquanto, só avisamos, mas não bloqueamos o rascunho
            
        order_item = SalesOrderItem(
            sales_order_id=order.id,
            product_id=item_in.product_id,
            quantity=item_in.quantity,
            unit_price=item_in.unit_price
        )
        db.add(order_item)
        total_amount += (item_in.quantity * item_in.unit_price)
        
    order.total_amount = total_amount
    
    try:
        await db.commit()
        await db.refresh(order, ['items'])
        
        # Auditoria
        new_data = {
            "id": str(order.id), "customer_id": str(order.customer_id), 
            "status": order.status, "total_amount": float(order.total_amount)
        }
        await log_audit_event(db, tenant_id, None, "INSERT", "sales_orders", str(order.id), None, new_data)
        await db.commit()
        
        return order
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[SalesOrderResponse])
async def list_sales_orders(
    skip: int = 0, limit: int = 50,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(SalesOrder).where(SalesOrder.tenant_id == tenant_id).options(selectinload(SalesOrder.items)).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.patch("/{order_id}/status", response_model=SalesOrderResponse)
async def update_sales_order_status(
    order_id: UUID,
    status_update: SalesOrderStatusUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(SalesOrder).where(SalesOrder.id == order_id, SalesOrder.tenant_id == tenant_id).options(selectinload(SalesOrder.items))
    result = await db.execute(query)
    order = result.scalars().first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Pedido de Venda não encontrado")

    old_status = order.status
    new_status = status_update.status.upper()
    
    if old_status == new_status:
        return order

    # Impede voltar atrás se já foi entregue ou cancelado (opcional, regra de negócio)
    if old_status in ["DELIVERED", "CANCELLED"]:
        raise HTTPException(status_code=400, detail=f"Não é possível alterar o status de um pedido já {old_status}.")

    order.status = new_status
    
    # GATILHO LOGÍSTICO: Se o status mudar para SHIPPED (Enviado), fazemos a baixa no estoque
    if new_status == "SHIPPED" and old_status != "SHIPPED":
        for item in order.items:
            # Busca o produto com lock para garantir a transação atômica
            query_prod = select(Product).where(Product.id == item.product_id).with_for_update()
            product = (await db.execute(query_prod)).scalars().first()
            
            if not product:
                raise HTTPException(status_code=404, detail="Produto do pedido não encontrado no banco.")
                
            if product.current_stock < item.quantity:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Estoque insuficiente para o produto {product.name}. Necessário: {item.quantity}, Disponível: {product.current_stock}"
                )
                
            # Atualiza o estoque
            product.current_stock -= item.quantity
            
            # Registra a transação OUT
            transaction = InventoryTransaction(
                tenant_id=tenant_id,
                product_id=product.id,
                user_id=user.id,
                transaction_type="OUT",
                quantity=item.quantity,
                unit_cost=product.cost_price, # Custo da mercadoria no momento da saída (para DRE)
                unit_price=item.unit_price,   # Preço de venda cobrado no pedido
                notes=f"Venda - Pedido #{str(order.id)[:8]}"
            )
            db.add(transaction)

    # Auditoria
    old_data = {"status": old_status}
    new_data = {"status": new_status}
    
    try:
        await log_audit_event(db, tenant_id, user.id, "UPDATE", "sales_orders", str(order.id), old_data, new_data)
        await db.commit()
        await db.refresh(order)
        return order
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
