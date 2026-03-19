from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.deps import get_db, get_tenant_id
from app.models.transaction import InventoryTransaction
from app.models.product import Product
from app.schemas.transaction import TransactionCreate, TransactionResponse

router = APIRouter()

@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    transaction_in: TransactionCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Registra uma nova movimentação de estoque (Entrada/Saída).
    Atualiza atomicamente o saldo do produto.
    """
    # 1. Busca o produto garantindo que pertence ao tenant
    query = select(Product).where(
        Product.id == transaction_in.product_id, 
        Product.tenant_id == tenant_id
    ).with_for_update() # Bloqueia a linha para evitar race condition
    
    result = await db.execute(query)
    product = result.scalars().first()

    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")

    # 2. Lógica de Atualização de Estoque
    if transaction_in.type == 'OUT':
        if product.current_stock < transaction_in.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Estoque insuficiente. Atual: {product.current_stock}, Solicitado: {transaction_in.quantity}"
            )
        product.current_stock -= transaction_in.quantity
    
    elif transaction_in.type == 'IN':
        product.current_stock += transaction_in.quantity

    # 3. Cria o registro da transação capturando o preço de venda e custo no momento do registro
    db_transaction = InventoryTransaction(
        tenant_id=tenant_id,
        product_id=transaction_in.product_id,
        quantity=transaction_in.quantity,
        type=transaction_in.type,
        unit_price=product.price,
        unit_cost=product.cost_price
    )
    
    db.add(db_transaction)
    
    # O commit efetiva ambas as operações (update produto + insert transação)
    await db.commit()
    await db.refresh(db_transaction)
    
    return db_transaction
