from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Dict, Any
from pydantic import BaseModel
from uuid import UUID

from app.core.deps import get_db, get_tenant_id
from app.models.collection_order import CollectionOrder
from app.models.collection_order_item import CollectionOrderItem
from app.models.distribution_center import DistributionCenter
from app.schemas.collection_order import CollectionOrderCreate, CollectionOrderResponse, CollectionOrderUpdate, CollectionOrderStatusUpdate
from app.services.routing_service import calculate_route

router = APIRouter()

@router.get("/", response_model=List[CollectionOrderResponse])
async def list_collection_orders(
    skip: int = 0,
    limit: int = 50,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista as ordens de coleta do tenant atual com seus itens.
    """
    query = select(CollectionOrder).options(selectinload(CollectionOrder.items)).where(CollectionOrder.tenant_id == tenant_id).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/", response_model=CollectionOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_collection_order(
    collection_in: CollectionOrderCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Cria uma nova ordem de coleta com os itens (SKUs).
    """
    collection_data = collection_in.model_dump(exclude={"items"})
    
    new_collection = CollectionOrder(
        **collection_data,
        tenant_id=tenant_id
    )
    db.add(new_collection)
    await db.flush() # Para gerar o ID da coleta

    if collection_in.items:
        for item in collection_in.items:
            new_item = CollectionOrderItem(
                collection_order_id=new_collection.id,
                product_id=item.product_id,
                quantity=item.quantity,
                tenant_id=tenant_id
            )
            db.add(new_item)

    await db.commit()
    
    # Carrega a coleta com os itens recém criados para retornar no schema
    query = select(CollectionOrder).options(selectinload(CollectionOrder.items)).where(CollectionOrder.id == new_collection.id)
    result = await db.execute(query)
    return result.scalars().first()

class OptimizeCollectionRequest(BaseModel):
    collection_ids: List[UUID]
    vehicle_id: UUID

@router.post("/optimize-route", response_model=Dict[str, Any])
async def optimize_collection_route(
    request: OptimizeCollectionRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Roteiriza as ordens de coleta selecionadas partindo do CD principal.
    """
    if not request.collection_ids:
        raise HTTPException(status_code=400, detail="Nenhuma ordem de coleta selecionada.")

    # 1. Fetch collection orders
    query_orders = select(CollectionOrder).where(
        CollectionOrder.id.in_(request.collection_ids),
        CollectionOrder.tenant_id == tenant_id
    )
    result_orders = await db.execute(query_orders)
    orders = result_orders.scalars().all()

    if not orders:
        raise HTTPException(status_code=404, detail="Ordens de coleta não encontradas.")

    # 2. Get Distribution Center
    query_cd = select(DistributionCenter).where(
        DistributionCenter.tenant_id == tenant_id,
        DistributionCenter.is_active == True
    )
    result_cd = await db.execute(query_cd)
    cd = result_cd.scalars().first()

    ponto_zero = "Praça da Sé, São Paulo, SP, 01001-000, Brazil" # fallback
    if cd:
        ponto_zero = f"{cd.address}, {cd.city}, {cd.state}, {cd.zip_code}"

    addresses = [ponto_zero]
    
    # Force strict formatting for Geopy if possible, or just use pickup_address directly
    for order in orders:
        addr = order.pickup_address
        if not addr or len(addr.strip()) < 5:
             addr = "Praça da Sé, São Paulo, SP, 01001-000, Brazil" # fallback
        addresses.append(addr)

    try:
        routing_result = await calculate_route(addresses)
        if "error" in routing_result:
            raise HTTPException(status_code=400, detail=routing_result["error"])

        # Update status to ROUTED
        for order in orders:
            order.status = "ROUTED"
        await db.commit()

        # Build response sequence
        optimized_sequence = []
        sequence = routing_result["sequence"]
        sequence_coords = routing_result.get("sequence_coordinates", [])
        for i, seq_index in enumerate(sequence):
            if seq_index > 0 and seq_index <= len(orders):
                order_index = seq_index - 1
                lat, lng = (0.0, 0.0)
                if i < len(sequence_coords):
                    lat, lng = sequence_coords[i]
                optimized_sequence.append({
                    "order_id": str(orders[order_index].id),
                    "optimized_position": len(optimized_sequence) + 1,
                    "lat": lat,
                    "lng": lng
                })

        return {
            "vehicle_id": str(request.vehicle_id),
            "optimized_orders": optimized_sequence,
            "total_distance_km": routing_result["total_distance_km"],
            "total_eta_minutes": routing_result["total_eta_minutes"],
            "geometry": routing_result.get("geometry", {}),
            "steps": routing_result.get("steps", [])
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao otimizar rota: {str(e)}")

@router.patch("/{collection_id}/status", response_model=CollectionOrderResponse)
async def update_collection_status(
    collection_id: UUID,
    status_update: CollectionOrderStatusUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Atualiza o status de uma ordem de coleta.
    """
    query = select(CollectionOrder).where(
        CollectionOrder.id == collection_id,
        CollectionOrder.tenant_id == tenant_id
    )
    result = await db.execute(query)
    order = result.scalars().first()

    if not order:
        raise HTTPException(status_code=404, detail="Ordem de coleta não encontrada.")

    order.status = status_update.status
    await db.commit()
    await db.refresh(order)
    
    return order
