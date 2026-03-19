from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.core.security import get_password_hash
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(User).where(User.tenant_id == current_user.tenant_id)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id)
    result = await db.execute(query)
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return user

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas administradores podem criar usuários.")

    # Check if email exists
    query = select(User).where(User.email == user_in.email)
    result = await db.execute(query)
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")

    new_user = User(
        tenant_id=current_user.tenant_id,
        name=user_in.name,
        email=user_in.email,
        role=user_in.role,
        is_active=user_in.is_active,
        hashed_password=get_password_hash(user_in.password)
    )
    
    db.add(new_user)
    await db.flush() # Para gerar o ID

    await log_audit_event(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="CREATE",
        table_name="users",
        record_id=str(new_user.id),
        new_data={"name": new_user.name, "email": new_user.email, "role": new_user.role}
    )

    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas administradores podem editar usuários.")

    query = select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id)
    result = await db.execute(query)
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_data = {"name": user.name, "email": user.email, "role": user.role, "is_active": user.is_active}

    if user_in.email and user_in.email != user.email:
        # Check if new email exists
        query_email = select(User).where(User.email == user_in.email)
        res_email = await db.execute(query_email)
        if res_email.scalars().first():
            raise HTTPException(status_code=400, detail="E-mail já cadastrado.")
        user.email = user_in.email

    if user_in.name is not None:
        user.name = user_in.name
    if user_in.role is not None:
        user.role = user_in.role
    if user_in.is_active is not None:
        user.is_active = user_in.is_active
    if user_in.password:
        user.hashed_password = get_password_hash(user_in.password)

    new_data = {"name": user.name, "email": user.email, "role": user.role, "is_active": user.is_active}

    await log_audit_event(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="UPDATE",
        table_name="users",
        record_id=str(user.id),
        old_data=old_data,
        new_data=new_data
    )

    await db.commit()
    await db.refresh(user)
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas administradores podem excluir usuários.")

    query = select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id)
    result = await db.execute(query)
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_data = {"name": user.name, "email": user.email, "role": user.role}

    await db.delete(user)
    
    await log_audit_event(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="DELETE",
        table_name="users",
        record_id=str(user.id),
        old_data=old_data
    )

    await db.commit()
