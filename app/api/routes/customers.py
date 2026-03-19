from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from typing import List
from uuid import UUID

from app.core.deps import get_db, get_tenant_id
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate
from app.services.audit_service import log_audit_event

router = APIRouter()

@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer_in: CustomerCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    customer = Customer(**customer_in.model_dump(), tenant_id=tenant_id)
    db.add(customer)
    
    try:
        await db.commit()
        await db.refresh(customer)
        
        # Auditoria
        new_data = {c.name: getattr(customer, c.name) for c in customer.__table__.columns}
        await log_audit_event(db, tenant_id, None, "INSERT", "customers", str(customer.id), None, new_data)
        await db.commit()
        
        return customer
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Já existe um cliente com este documento (CPF/CNPJ).")

@router.get("/", response_model=List[CustomerResponse])
async def list_customers(
    skip: int = 0, limit: int = 50,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(Customer).where(Customer.tenant_id == tenant_id).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
    result = await db.execute(query)
    customer = result.scalars().first()
    
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return customer

@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: UUID,
    customer_in: CustomerUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
    result = await db.execute(query)
    customer = result.scalars().first()
    
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    old_data = {c.name: getattr(customer, c.name) for c in customer.__table__.columns}
    update_data = customer_in.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(customer, key, value)

    try:
        new_data = {c.name: getattr(customer, c.name) for c in customer.__table__.columns}
        await log_audit_event(db, tenant_id, None, "UPDATE", "customers", str(customer.id), old_data, new_data)
        
        await db.commit()
        await db.refresh(customer)
        return customer
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Documento já está em uso por outro cliente.")

@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
    result = await db.execute(query)
    customer = result.scalars().first()
    
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
        
    old_data = {c.name: getattr(customer, c.name) for c in customer.__table__.columns}
    await db.delete(customer)
    
    await log_audit_event(db, tenant_id, None, "DELETE", "customers", str(customer_id), old_data, None)
    await db.commit()
