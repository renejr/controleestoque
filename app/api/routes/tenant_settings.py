from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.deps import get_db, get_tenant_id, get_current_user
from app.models.tenant_setting import TenantSetting
from app.models.user import User
from app.schemas.tenant_setting import TenantSettingResponse, TenantSettingUpdate

router = APIRouter()

@router.get("/", response_model=TenantSettingResponse)
async def get_tenant_settings(
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(TenantSetting).where(TenantSetting.tenant_id == tenant_id)
    result = await db.execute(query)
    settings = result.scalars().first()
    
    if not settings:
        # Se não existir, cria um padrão na hora
        settings = TenantSetting(tenant_id=tenant_id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
        
    return settings

@router.put("/", response_model=TenantSettingResponse)
async def update_tenant_settings(
    settings_in: TenantSettingUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != 'ADMIN':
        raise HTTPException(status_code=403, detail="Apenas ADMIN pode alterar as configurações da empresa.")
        
    query = select(TenantSetting).where(TenantSetting.tenant_id == tenant_id)
    result = await db.execute(query)
    settings = result.scalars().first()
    
    if not settings:
        settings = TenantSetting(tenant_id=tenant_id)
        db.add(settings)
        
    update_data = settings_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings, key, value)
        
    await db.commit()
    await db.refresh(settings)
    return settings
