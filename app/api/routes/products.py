from typing import List, Optional
from uuid import UUID
import asyncio
import csv
import io
import decimal
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from sqlalchemy.exc import IntegrityError

from app.core.deps import get_db, get_tenant_id
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services.audit_service import log_audit_event
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
    
    # Captura o estado antigo para auditoria (convertendo o objeto para dict)
    # Excluímos o _sa_instance_state que é interno do SQLAlchemy e o embedding que é gigante
    old_data = {c.name: getattr(product, c.name) for c in product.__table__.columns if c.name != 'embedding'}

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
        # Captura o estado novo
        new_data = {c.name: getattr(product, c.name) for c in product.__table__.columns if c.name != 'embedding'}
        
        # Registra a auditoria ANTES do commit
        # TODO: Quando a rota receber o current_user, passar o user_id real em vez de None
        await log_audit_event(
            db=db,
            tenant_id=tenant_id,
            user_id=None, 
            action="UPDATE",
            table_name="products",
            record_id=str(product.id),
            old_data=old_data,
            new_data=new_data
        )

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

@router.post("/import", status_code=status.HTTP_200_OK)
async def import_products_csv(
    file: UploadFile = File(...),
    dry_run: bool = Form(True),
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Importa produtos em lote a partir de um arquivo CSV.
    Se dry_run=True, apenas valida o arquivo e retorna um relatório de erros.
    Se dry_run=False, realiza a validação e, se não houver erros impeditivos (ou ignorando as linhas com erro), insere os válidos no banco.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="O arquivo deve ser um .csv")

    contents = await file.read()
    decoded_contents = contents.decode('utf-8-sig') # lida com BOM se houver
    
    # Lê o CSV
    csv_reader = csv.DictReader(io.StringIO(decoded_contents), delimiter=',')
    
    # Padroniza as chaves do cabeçalho (remove espaços e converte para minúsculo)
    if csv_reader.fieldnames:
        csv_reader.fieldnames = [field.strip().lower() for field in csv_reader.fieldnames]

    required_columns = {'name', 'sku', 'price', 'cost_price'}
    if not required_columns.issubset(set(csv_reader.fieldnames or [])):
        missing = required_columns - set(csv_reader.fieldnames or [])
        raise HTTPException(status_code=400, detail=f"O arquivo CSV não contém as colunas obrigatóricas: {missing}")

    # Busca SKUs já existentes no banco para este tenant para validação rápida
    query_skus = select(Product.sku).where(Product.tenant_id == tenant_id)
    result_skus = await db.execute(query_skus)
    existing_skus = {row[0] for row in result_skus.all() if row[0]}

    errors = []
    valid_products_data = []
    file_skus = set()
    
    line_number = 1 # Cabeçalho é a linha 1

    for row in csv_reader:
        line_number += 1
        line_errors = []
        
        # Extração de campos básicos
        name = row.get('name', '').strip()
        sku = row.get('sku', '').strip()
        barcode = row.get('barcode', '').strip() or None
        
        # Validação de nome e SKU
        if not name:
            line_errors.append("Nome do produto é obrigatório.")
        if not sku:
            line_errors.append("SKU é obrigatório.")
        else:
            if sku in existing_skus:
                line_errors.append(f"O SKU '{sku}' já existe no banco de dados.")
            if sku in file_skus:
                line_errors.append(f"O SKU '{sku}' está duplicado neste arquivo CSV.")
            file_skus.add(sku)

        # Conversão e validação de números
        try:
            price = decimal.Decimal(row.get('price', '0').replace(',', '.'))
            if price <= 0:
                line_errors.append("Preço de venda deve ser maior que zero.")
        except decimal.InvalidOperation:
            line_errors.append("Formato inválido para Preço de Venda.")
            price = decimal.Decimal('0')

        try:
            cost_price = decimal.Decimal(row.get('cost_price', '0').replace(',', '.'))
            if cost_price < 0:
                line_errors.append("Preço de custo não pode ser negativo.")
        except decimal.InvalidOperation:
            line_errors.append("Formato inválido para Preço de Custo.")
            cost_price = decimal.Decimal('0')
            
        try:
            min_stock = int(row.get('min_stock', '0'))
        except ValueError:
            line_errors.append("Estoque mínimo deve ser um número inteiro.")
            min_stock = 0
            
        # Extração de campos opcionais e fiscais
        description = row.get('description', '').strip() or None
        category = row.get('category', '').strip() or None
        ncm = row.get('ncm', '').strip() or None
        cfop = row.get('cfop', '').strip() or None
        cest = row.get('cest', '').strip() or None
        
        try:
            origin = int(row.get('origin', '0'))
        except ValueError:
            origin = 0

        if line_errors:
            errors.append({"line": line_number, "sku": sku, "errors": line_errors})
        else:
            # Prepara o dict para inserção se for válido
            valid_products_data.append({
                "tenant_id": tenant_id,
                "name": name,
                "description": description,
                "sku": sku,
                "barcode": barcode,
                "category": category,
                "price": price,
                "cost_price": cost_price,
                "min_stock": min_stock,
                "current_stock": 0, # Estoque inicial é sempre 0 na importação de cadastro
                "ncm": ncm,
                "cfop": cfop,
                "cest": cest,
                "origin": origin
            })

    total_processed = line_number - 1
    valid_count = len(valid_products_data)

    # Se for Dry-Run, apenas retorna o relatório
    if dry_run:
        return {
            "dry_run": True,
            "total_processed": total_processed,
            "valid_count": valid_count,
            "error_count": len(errors),
            "errors": errors
        }

    # Se não for Dry-Run, insere no banco
    if valid_count > 0:
        # Gera embeddings em paralelo para não travar muito o loop
        loop = asyncio.get_running_loop()
        
        # Função auxiliar para gerar um Product com embedding
        async def create_product_with_embedding(p_data):
            text_to_embed = f"{p_data['name']} {p_data['description'] or ''}"
            vector = await loop.run_in_executor(None, embedding_service.generate_embedding, text_to_embed)
            p_data['embedding'] = vector
            return Product(**p_data)

        # Processa todos de forma assíncrona
        product_objects = await asyncio.gather(
            *[create_product_with_embedding(data) for data in valid_products_data]
        )
        
        db.add_all(product_objects)
        
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Erro crítico no banco de dados durante a importação em lote. Nenhuma linha foi salva. Detalhes: {str(e.orig)}")

    return {
        "dry_run": False,
        "total_processed": total_processed,
        "inserted_count": valid_count,
        "error_count": len(errors),
        "errors": errors,
        "message": f"{valid_count} produtos importados com sucesso."
    }
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
