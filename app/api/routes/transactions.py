from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.deps import get_db, get_tenant_id
from app.models.transaction import InventoryTransaction
from app.models.product import Product
from app.schemas.transaction import TransactionCreate, TransactionResponse, StockTransferRequest

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

@router.post("/transfer", status_code=status.HTTP_200_OK)
async def transfer_stock(
    transfer_in: StockTransferRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Realiza uma transferência de estoque atômica entre dois CDs.
    Cria uma transação OUT na origem e uma IN no destino.
    """
    if transfer_in.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantidade deve ser maior que zero.")

    # Busca o produto na origem (para validar estoque e clonar)
    query_source = select(Product).where(
        Product.id == transfer_in.product_id,
        Product.tenant_id == tenant_id,
        Product.cd_id == transfer_in.source_cd_id
    ).with_for_update()
    
    result_source = await db.execute(query_source)
    source_product = result_source.scalars().first()

    if not source_product:
        raise HTTPException(status_code=404, detail="Produto não encontrado no CD de origem.")

    if source_product.current_stock < transfer_in.quantity:
        raise HTTPException(status_code=400, detail=f"Estoque insuficiente na origem. Saldo: {source_product.current_stock}")

    # Busca o produto no destino (mesmo SKU, mesmo Tenant, CD diferente)
    query_dest = select(Product).where(
        Product.sku == source_product.sku,
        Product.tenant_id == tenant_id,
        Product.cd_id == transfer_in.destination_cd_id
    ).with_for_update()
    
    result_dest = await db.execute(query_dest)
    dest_product = result_dest.scalars().first()

    # Se não existir no destino, cria um clone com estoque zero antes de transferir
    if not dest_product:
        dest_product = Product(
            tenant_id=tenant_id,
            name=source_product.name,
            sku=source_product.sku,
            barcode=source_product.barcode,
            description=source_product.description,
            price=source_product.price,
            cost_price=source_product.cost_price,
            current_stock=0,
            min_stock=source_product.min_stock,
            weight=source_product.weight,
            width=source_product.width,
            height=source_product.height,
            length=source_product.length,
            ncm=source_product.ncm,
            cfop=source_product.cfop,
            cest=source_product.cest,
            origin=source_product.origin,
            cd_id=transfer_in.destination_cd_id
        )
        db.add(dest_product)
        await db.flush() # Para garantir o ID

    # --- INÍCIO DA OPERAÇÃO ATÔMICA ---
    
    # 1. Debita da origem
    source_product.current_stock -= transfer_in.quantity
    source_product.version += 1
    
    # 2. Credita no destino
    dest_product.current_stock += transfer_in.quantity
    dest_product.version += 1

    # 3. Registra Log OUT na origem
    tx_out = InventoryTransaction(
        tenant_id=tenant_id,
        product_id=source_product.id,
        quantity=transfer_in.quantity,
        type='OUT',
        unit_price=source_product.price,
        unit_cost=source_product.cost_price,
        notes=f"{transfer_in.notes} (Para CD: {transfer_in.destination_cd_id})"
    )
    
    # 4. Registra Log IN no destino
    tx_in = InventoryTransaction(
        tenant_id=tenant_id,
        product_id=dest_product.id,
        quantity=transfer_in.quantity,
        type='IN',
        unit_price=dest_product.price,
        unit_cost=dest_product.cost_price,
        notes=f"{transfer_in.notes} (De CD: {transfer_in.source_cd_id})"
    )

    db.add(tx_out)
    db.add(tx_in)
    
    await db.commit()
    
    return {"message": "Transferência realizada com sucesso."}
