from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from uuid import UUID

from app.core.deps import get_db, get_tenant_id
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderResponse, PurchaseOrderUpdate

router = APIRouter()

@router.post("/", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    order_in: PurchaseOrderCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Cria uma nova Ordem de Compra.
    """
    db_order = PurchaseOrder(
        tenant_id=tenant_id,
        supplier_id=order_in.supplier_id,
        status=order_in.status,
        total_amount=order_in.total_amount,
        notes=order_in.notes
    )
    
    db.add(db_order)
    await db.flush() # Para gerar o ID da ordem
    
    for item in order_in.items:
        db_item = PurchaseOrderItem(
            purchase_order_id=db_order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=item.unit_price
        )
        db.add(db_item)
        
    await db.commit()
    
    # Recarrega a ordem com os itens
    query = select(PurchaseOrder).options(selectinload(PurchaseOrder.items)).where(PurchaseOrder.id == db_order.id)
    result = await db.execute(query)
    return result.scalar_one()

@router.get("/", response_model=List[PurchaseOrderResponse])
async def list_purchase_orders(
    skip: int = 0,
    limit: int = 20,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista as Ordens de Compra do tenant atual.
    """
    query = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.items))
        .where(PurchaseOrder.tenant_id == tenant_id)
        .order_by(PurchaseOrder.order_date.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{order_id}", response_model=PurchaseOrderResponse)
async def get_purchase_order(
    order_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Retorna os detalhes de uma Ordem de Compra específica.
    """
    query = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.items))
        .where(PurchaseOrder.id == order_id, PurchaseOrder.tenant_id == tenant_id)
    )
    result = await db.execute(query)
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Ordem de compra não encontrada")
    return order

@router.put("/{order_id}", response_model=PurchaseOrderResponse)
async def update_purchase_order(
    order_id: UUID,
    order_in: PurchaseOrderUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Atualiza status, total ou notas da Ordem de Compra.
    (Atualização de itens fica para a Fase 2 do módulo).
    """
    query = select(PurchaseOrder).options(selectinload(PurchaseOrder.items)).where(PurchaseOrder.id == order_id, PurchaseOrder.tenant_id == tenant_id)
    result = await db.execute(query)
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Ordem de compra não encontrada")
        
    update_data = order_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(order, key, value)
        
    await db.commit()
    await db.refresh(order)
    return order

@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_purchase_order(
    order_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Exclui uma Ordem de Compra (e seus itens via cascade).
    """
    query = select(PurchaseOrder).where(PurchaseOrder.id == order_id, PurchaseOrder.tenant_id == tenant_id)
    result = await db.execute(query)
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Ordem de compra não encontrada")
        
    await db.delete(order)
    await db.commit()
