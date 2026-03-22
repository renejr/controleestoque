from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.deps import get_db, get_tenant_id, get_current_user
from app.models.distribution_center import DistributionCenter
from app.models.user import User
from app.schemas.distribution_center import DistributionCenterCreate, DistributionCenterUpdate, DistributionCenterResponse

router = APIRouter()

@router.get("/", response_model=List[DistributionCenterResponse])
async def list_distribution_centers(
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(DistributionCenter).where(DistributionCenter.tenant_id == tenant_id)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/", response_model=DistributionCenterResponse, status_code=status.HTTP_201_CREATED)
async def create_distribution_center(
    cd_in: DistributionCenterCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ['ADMIN', 'MANAGER']:
        raise HTTPException(status_code=403, detail="Acesso negado. Apenas ADMIN e MANAGER podem criar CDs.")
        
    new_cd = DistributionCenter(
        tenant_id=tenant_id,
        **cd_in.model_dump()
    )
    db.add(new_cd)
    await db.commit()
    await db.refresh(new_cd)
    return new_cd

@router.put("/{cd_id}", response_model=DistributionCenterResponse)
async def update_distribution_center(
    cd_id: UUID,
    cd_in: DistributionCenterUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ['ADMIN', 'MANAGER']:
        raise HTTPException(status_code=403, detail="Acesso negado. Apenas ADMIN e MANAGER podem editar CDs.")
        
    query = select(DistributionCenter).where(DistributionCenter.id == cd_id, DistributionCenter.tenant_id == tenant_id)
    result = await db.execute(query)
    cd = result.scalars().first()
    
    if not cd:
        raise HTTPException(status_code=404, detail="Centro de Distribuição não encontrado.")
        
    update_data = cd_in.model_dump(exclude_unset=True)
    
    if 'version' in update_data:
        client_version = update_data.pop('version')
        if client_version != cd.version:
            current_state = {c.name: getattr(cd, c.name) for c in cd.__table__.columns}
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Conflito de versão detectado. O CD foi modificado por outro usuário.",
                    "current_state": current_state
                }
            )
            
    cd.version += 1
    
    for key, value in update_data.items():
        setattr(cd, key, value)
        
    await db.commit()
    await db.refresh(cd)
    return cd

@router.delete("/{cd_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_distribution_center(
    cd_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ['ADMIN', 'MANAGER']:
        raise HTTPException(status_code=403, detail="Acesso negado. Apenas ADMIN e MANAGER podem excluir CDs.")
        
    query = select(DistributionCenter).where(DistributionCenter.id == cd_id, DistributionCenter.tenant_id == tenant_id)
    result = await db.execute(query)
    cd = result.scalars().first()
    
    if not cd:
        raise HTTPException(status_code=404, detail="Centro de Distribuição não encontrado.")
        
    await db.delete(cd)
    await db.commit()
