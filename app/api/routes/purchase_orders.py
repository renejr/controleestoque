from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, cast, String
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID

from app.core.deps import get_db, get_tenant_id
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.transaction import InventoryTransaction
from app.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderResponse, PurchaseOrderUpdate
from app.services.audit_service import log_audit_event

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
        cd_id=order_in.cd_id,
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
    limit: int = 50,
    search: Optional[str] = Query(None, description="Busca por número da ordem (ID) ou nome do fornecedor"),
    status: Optional[str] = Query(None, description="Filtra por status da ordem"),
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista as Ordens de Compra do tenant atual.
    """
    query = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.items))
        .join(Supplier, PurchaseOrder.supplier_id == Supplier.id)
        .where(PurchaseOrder.tenant_id == tenant_id)
    )

    if search:
        # Busca no ID da ordem (cast para string) ou no nome do fornecedor
        query = query.where(
            or_(
                cast(PurchaseOrder.id, String).ilike(f"%{search}%"),
                Supplier.name.ilike(f"%{search}%")
            )
        )

    if status and status.upper() != "TODOS":
        query = query.where(PurchaseOrder.status == status.upper())

    query = query.order_by(PurchaseOrder.order_date.desc()).offset(skip).limit(limit)

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
        
    previous_status = order.status
    
    # Captura o estado antigo para auditoria
    old_data = {c.name: getattr(order, c.name) for c in order.__table__.columns}
    
    update_data = order_in.model_dump(exclude_unset=True)
    
    # Validação de Versão para Controle de Concorrência Otimista (OCC)
    if 'version' in update_data:
        client_version = update_data.pop('version')
        if client_version != order.version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Conflito de versão detectado. A ordem de compra foi modificada por outro usuário.",
                    "current_state": old_data
                }
            )
            
    order.version += 1
    
    try:
        for key, value in update_data.items():
            setattr(order, key, value)
            
        # Captura o estado novo
        new_data = {c.name: getattr(order, c.name) for c in order.__table__.columns}
        
        # Registra a auditoria
        await log_audit_event(
            db=db,
            tenant_id=tenant_id,
            user_id=None, # TODO: injetar usuário logado no futuro
            action="UPDATE",
            table_name="purchase_orders",
            record_id=str(order.id),
            old_data=old_data,
            new_data=new_data
        )
             
        # Gatilho: Se o status mudou para RECEIVED, processa a entrada no estoque no CD destino
        if previous_status != "RECEIVED" and order.status == "RECEIVED":
            if not order.cd_id:
                raise ValueError("Não é possível receber a ordem sem um Centro de Distribuição (CD) de destino definido.")
                
            for item in order.items:
                # 1. Busca o produto (Garantindo que é do tenant, o CD pode não estar setado no produto mestre ainda)
                prod_query = select(Product).where(Product.id == item.product_id, Product.tenant_id == tenant_id).with_for_update()
                prod_result = await db.execute(prod_query)
                product = prod_result.scalar_one_or_none()
                
                if not product:
                    raise ValueError(f"Produto {item.product_id} não encontrado para entrada no estoque.")
                    
                # Se o produto não tiver CD definido, ou se estiver num CD diferente, precisamos ajustar a lógica.
                # Para simplificar na versão atual, vamos criar a transação IN amarrada ao produto.
                # Idealmente o produto deveria estar amarrado ao CD da ordem, ou deveria haver um clone.
                # Vamos assumir que a transação entra no CD da ordem e o produto passa a pertencer a esse CD se for órfão.
                if not product.cd_id:
                    product.cd_id = order.cd_id

                # 2. Cria a transação de IN (Entrada) amarrada ao produto
                transaction = InventoryTransaction(
                    tenant_id=tenant_id,
                    product_id=product.id,
                    type="IN",
                    quantity=int(item.quantity), # Estoque geralmente é int na nossa regra atual
                    unit_cost=item.unit_price,
                    unit_price=product.price # Mantém o preço de venda atual do produto
                )
                db.add(transaction)
                
                # 3. Atualiza o estoque atual do produto
                product.current_stock += int(item.quantity)
                product.version += 1

        await db.commit()
        await db.refresh(order)
        return order
        
    except ValueError as ve:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro interno ao processar ordem de compra e estoque: {str(e)}")

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
