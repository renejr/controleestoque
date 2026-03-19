from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.deps import get_db, get_tenant_id
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantResponse, TenantUpdate

router = APIRouter()

@router.get("/me", response_model=TenantResponse)
async def get_my_tenant(
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtém os detalhes do Tenant do usuário logado.
    """
    query = select(Tenant).where(Tenant.id == tenant_id)
    result = await db.execute(query)
    tenant = result.scalars().first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado.")
    return tenant

@router.put("/me", response_model=TenantResponse)
async def update_my_tenant(
    tenant_in: TenantUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Atualiza os dados do Tenant do usuário logado.
    """
    query = select(Tenant).where(Tenant.id == tenant_id)
    result = await db.execute(query)
    tenant = result.scalars().first()
    
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado.")
    
    update_data = tenant_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)
        
    await db.commit()
    await db.refresh(tenant)
    return tenant

@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant_in: TenantCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Cria um novo Tenant (Empresa/Cliente) no SaaS.
    Acesso restrito a Super Admin.
    """
    db_tenant = Tenant(**tenant_in.model_dump())
    db.add(db_tenant)
    await db.commit()
    await db.refresh(db_tenant)
    return db_tenant

@router.get("/", response_model=List[TenantResponse])
async def list_tenants(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    Lista todos os Tenants cadastrados na plataforma.
    Acesso restrito a Super Admin.
    """
    query = select(Tenant).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Obtém os detalhes de um Tenant específico pelo ID.
    Acesso restrito a Super Admin.
    """
    query = select(Tenant).where(Tenant.id == tenant_id)
    result = await db.execute(query)
    tenant = result.scalars().first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado.")
    return tenant

@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: UUID,
    tenant_in: TenantUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Atualiza os dados de um Tenant existente.
    Acesso restrito a Super Admin.
    """
    query = select(Tenant).where(Tenant.id == tenant_id)
    result = await db.execute(query)
    tenant = result.scalars().first()
    
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado.")
    
    update_data = tenant_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)
        
    await db.commit()
    await db.refresh(tenant)
    return tenant

@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Remove um Tenant do sistema.
    CUIDADO: Isso pode remover todos os dados associados (cascade delete).
    Acesso restrito a Super Admin.
    """
    query = select(Tenant).where(Tenant.id == tenant_id)
    result = await db.execute(query)
    tenant = result.scalars().first()
    
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado.")
    
    await db.delete(tenant)
    await db.commit()
    return None
