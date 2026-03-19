from typing import List
from uuid import UUID
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.deps import get_db, get_tenant_id
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services.embedding import embedding_service

router = APIRouter()

@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_in: ProductCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Cria um novo produto vinculado ao tenant_id.
    Gera automaticamente o embedding vetorial.
    """
    product_data = product_in.model_dump()
    
    # Gera o texto para embedding
    text_to_embed = f"{product_data.get('name', '')} {product_data.get('description', '')}"
    
    # Executa a geração do embedding em uma thread separada para não bloquear o loop
    loop = asyncio.get_running_loop()
    embedding_vector = await loop.run_in_executor(
        None, 
        embedding_service.generate_embedding, 
        text_to_embed
    )
    
    # Adiciona o vetor aos dados do produto
    product_data['embedding'] = embedding_vector

    db_product = Product(**product_data, tenant_id=tenant_id)
    db.add(db_product)
    try:
        await db.commit()
        await db.refresh(db_product)
        return db_product
    except IntegrityError as e:
        await db.rollback()
        error_msg = str(e.orig)
        if "uq_tenant_sku" in error_msg:
            raise HTTPException(status_code=400, detail="Já existe um produto com este SKU neste tenant.")
        if "uq_tenant_barcode" in error_msg:
            raise HTTPException(status_code=400, detail="Já existe um produto com este Código de Barras neste tenant.")
        raise HTTPException(status_code=400, detail="Erro de integridade ao criar produto.")

@router.get("/", response_model=List[ProductResponse])
async def list_products(
    skip: int = 0,
    limit: int = 20,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista os produtos vinculados ao tenant_id com paginação.
    """
    query = select(Product).where(Product.tenant_id == tenant_id).order_by(Product.name).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/search", response_model=List[ProductResponse])
async def search_products(
    q: str,
    limit: int = 5,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Realiza uma busca semântica por produtos usando vetores (pgvector).
    A busca é isolada pelo tenant_id e ordenada pela distância cosseno (relevância).
    """
    if not q:
        return []

    # 1. Gera o embedding da query do usuário (assíncrono para não bloquear)
    loop = asyncio.get_running_loop()
    query_vector = await loop.run_in_executor(
        None, 
        embedding_service.generate_embedding, 
        q
    )

    # 2. Busca no banco usando o operador de distância cosseno (<=> ou cosine_distance)
    # A função cosine_distance retorna a distância, então ordenamos de forma crescente (menor distância = maior similaridade)
    # Filtramos para que a distância seja menor que 0.5 (evitar resultados irrelevantes)
    query = (
        select(Product)
        .where(Product.tenant_id == tenant_id)
        .where(Product.embedding.cosine_distance(query_vector) < 0.5)
        .order_by(Product.embedding.cosine_distance(query_vector))
        .limit(limit)
    )

    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtém os detalhes de um produto pelo seu ID, garantindo que pertença ao tenant_id.
    """
    query = select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id)
    result = await db.execute(query)
    product = result.scalars().first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")
    return product

@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    product_in: ProductUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Atualiza um produto específico pertencente ao tenant_id.
    Recalcula o embedding se houver alteração em campos de texto.
    """
    query = select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id)
    result = await db.execute(query)
    product = result.scalars().first()
    
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")
    
    update_data = product_in.model_dump(exclude_unset=True)
    
    # Se houver alteração de nome ou descrição, recalcula o embedding
    if 'name' in update_data or 'description' in update_data:
        new_name = update_data.get('name', product.name)
        new_description = update_data.get('description', product.description or "")
        text_to_embed = f"{new_name} {new_description}"
        
        loop = asyncio.get_running_loop()
        embedding_vector = await loop.run_in_executor(
            None, 
            embedding_service.generate_embedding, 
            text_to_embed
        )
        update_data['embedding'] = embedding_vector

    for key, value in update_data.items():
        setattr(product, key, value)

    try:
        await db.commit()
        await db.refresh(product)
        return product
    except IntegrityError as e:
        await db.rollback()
        error_msg = str(e.orig)
        if "uq_tenant_sku" in error_msg:
            raise HTTPException(status_code=400, detail="Já existe um produto com este SKU neste tenant.")
        if "uq_tenant_barcode" in error_msg:
            raise HTTPException(status_code=400, detail="Já existe um produto com este Código de Barras neste tenant.")
        raise HTTPException(status_code=400, detail="Erro de integridade ao atualizar produto.")

@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove um produto específico pertencente ao tenant_id.
    """
    query = select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id)
    result = await db.execute(query)
    product = result.scalars().first()
    
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")
    
    await db.delete(product)
    await db.commit()
    return None
