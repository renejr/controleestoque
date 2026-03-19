from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from typing import List
from uuid import UUID

from app.core.deps import get_db, get_tenant_id
from app.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleResponse, VehicleUpdate
from app.services.audit_service import log_audit_event

router = APIRouter()

@router.post("/", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    vehicle_in: VehicleCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    vehicle = Vehicle(**vehicle_in.model_dump(), tenant_id=tenant_id)
    db.add(vehicle)
    
    try:
        await db.commit()
        await db.refresh(vehicle)
        
        # Auditoria (Insert)
        new_data = {c.name: getattr(vehicle, c.name) for c in vehicle.__table__.columns}
        await log_audit_event(
            db=db,
            tenant_id=tenant_id,
            user_id=None,
            action="INSERT",
            table_name="vehicles",
            record_id=str(vehicle.id),
            old_data=None,
            new_data=new_data
        )
        await db.commit()
        
        return vehicle
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Já existe um veículo com esta placa para este tenant.")

@router.get("/", response_model=List[VehicleResponse])
async def list_vehicles(
    skip: int = 0,
    limit: int = 50,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(Vehicle).where(Vehicle.tenant_id == tenant_id).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(
    vehicle_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.tenant_id == tenant_id)
    result = await db.execute(query)
    vehicle = result.scalars().first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Veículo não encontrado")
    return vehicle

@router.put("/{vehicle_id}", response_model=VehicleResponse)
async def update_vehicle(
    vehicle_id: UUID,
    vehicle_in: VehicleUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.tenant_id == tenant_id)
    result = await db.execute(query)
    vehicle = result.scalars().first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Veículo não encontrado")

    # Auditoria - Foto Antes
    old_data = {c.name: getattr(vehicle, c.name) for c in vehicle.__table__.columns}

    update_data = vehicle_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(vehicle, key, value)

    try:
        # Auditoria - Foto Depois
        new_data = {c.name: getattr(vehicle, c.name) for c in vehicle.__table__.columns}
        
        await log_audit_event(
            db=db,
            tenant_id=tenant_id,
            user_id=None,
            action="UPDATE",
            table_name="vehicles",
            record_id=str(vehicle.id),
            old_data=old_data,
            new_data=new_data
        )
        
        await db.commit()
        await db.refresh(vehicle)
        return vehicle
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Placa já está em uso por outro veículo.")

@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(
    vehicle_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.tenant_id == tenant_id)
    result = await db.execute(query)
    vehicle = result.scalars().first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Veículo não encontrado")
        
    # Auditoria - Foto Antes
    old_data = {c.name: getattr(vehicle, c.name) for c in vehicle.__table__.columns}

    await db.delete(vehicle)
    
    await log_audit_event(
        db=db,
        tenant_id=tenant_id,
        user_id=None,
        action="DELETE",
        table_name="vehicles",
        record_id=str(vehicle_id),
        old_data=old_data,
        new_data=None
    )
    
    await db.commit()
