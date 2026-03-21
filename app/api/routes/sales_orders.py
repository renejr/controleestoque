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
    user = Depends(get_current_user),
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
        notes=order_in.notes
    )
    db.add(order)
    await db.flush() # Para gerar o ID do pedido

    # Adiciona os itens
    total_amount = 0.0
    for item_in in order_in.items:
        # Pega o produto para validar e pegar o preço
        query_product = select(Product).where(Product.id == item_in.product_id, Product.tenant_id == tenant_id)
        product = (await db.execute(query_product)).scalars().first()
        
        if not product:
            raise HTTPException(status_code=404, detail=f"Produto {item_in.product_id} não encontrado.")
            
        unit_price = item_in.unit_price if item_in.unit_price else product.sale_price
        subtotal = unit_price * item_in.quantity
        total_amount += subtotal
        
        order_item = SalesOrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=item_in.quantity,
            unit_price=unit_price,
            subtotal=subtotal
        )
        db.add(order_item)
        
    order.total_amount = total_amount
    
    # Auditoria
    new_data = {"customer_id": str(order.customer_id), "total_amount": float(order.total_amount), "status": order.status}
    await log_audit_event(db, tenant_id, user.id, "INSERT", "sales_orders", str(order.id), None, new_data)
    
    await db.commit()
    await db.refresh(order)
    
    # Retorna com os itens carregados
    query = select(SalesOrder).options(selectinload(SalesOrder.items)).where(SalesOrder.id == order.id)
    return (await db.execute(query)).scalars().first()

@router.get("/", response_model=List[SalesOrderResponse])
async def get_sales_orders(
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(SalesOrder).options(selectinload(SalesOrder.items)).where(SalesOrder.tenant_id == tenant_id)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{order_id}", response_model=SalesOrderResponse)
async def get_sales_order(
    order_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(SalesOrder).options(selectinload(SalesOrder.items)).where(SalesOrder.id == order_id, SalesOrder.tenant_id == tenant_id)
    order = (await db.execute(query)).scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    return order

@router.patch("/{order_id}/status", response_model=SalesOrderResponse)
async def update_sales_order_status(
    order_id: UUID,
    status_update: SalesOrderStatusUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(SalesOrder).options(selectinload(SalesOrder.items)).where(SalesOrder.id == order_id, SalesOrder.tenant_id == tenant_id)
    order = (await db.execute(query)).scalars().first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
        
    old_status = order.status
    new_status = status_update.status
    
    if old_status == new_status:
        return order
        
    order.status = new_status
    
    # Se o pedido foi marcado como SHIPPED (enviado), precisamos dar baixa no estoque
    if new_status == "SHIPPED":
        for item in order.items:
            # Busca o produto para atualizar o estoque
            query_product = select(Product).where(Product.id == item.product_id, Product.tenant_id == tenant_id)
            product = (await db.execute(query_product)).scalars().first()
            
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
                type="OUT",
                quantity=item.quantity,
                unit_cost=product.cost_price, # Custo da mercadoria no momento da saída (para DRE)
                unit_price=item.unit_price    # Preço de venda cobrado no pedido
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
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar status: {str(e)}")