from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.deps import get_db, get_tenant_id
from app.models.vehicle import Vehicle
from app.models.product import Product
from app.schemas.fleet import PackOrderRequest
from app.services.logistics_service import calculate_packing
from app.services.routing_service import calculate_route
from app.models.sales_order import SalesOrder

router = APIRouter()

@router.post("/pack-order", status_code=status.HTTP_200_OK)
async def simulate_pack_order(
    request_data: PackOrderRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Simula o carregamento (Bin Packing) de uma lista de produtos dentro de um veículo específico.
    """
    
    # 1. Busca o Veículo garantindo que pertence ao Tenant atual
    query_vehicle = select(Vehicle).where(Vehicle.id == request_data.vehicle_id, Vehicle.tenant_id == tenant_id)
    result_vehicle = await db.execute(query_vehicle)
    vehicle = result_vehicle.scalars().first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Veículo não encontrado ou não pertence à sua frota.")

    # 2. Busca e Valida os Produtos
    products_to_pack = []
    
    for req_item in request_data.items:
        query_product = select(Product).where(Product.id == req_item.product_id, Product.tenant_id == tenant_id)
        result_product = await db.execute(query_product)
        product = result_product.scalars().first()
        
        if not product:
            raise HTTPException(status_code=404, detail=f"Produto {req_item.product_id} não encontrado.")
            
        # Adiciona a quantidade de itens solicitada
        for _ in range(req_item.quantity):
            products_to_pack.append({
                "id": str(product.id),
                "name": product.name,  # <--- A CEREJA DO BOLO: O NOME INJETADO AQUI!
                "width": product.width,
                "height": product.height,
                "length": product.length,
                "weight": product.weight
            })

    # 3. Executa o Motor de Cubagem
    try:
        packing_report = calculate_packing(vehicle, products_to_pack)
        return packing_report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno no motor de cubagem: {str(e)}")

@router.post("/optimize-route", status_code=status.HTTP_200_OK)
async def optimize_fleet_route(
    romaneio_id: str,
    sales_orders_ids: list[UUID],
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query_orders = select(SalesOrder).where(SalesOrder.id.in_(sales_orders_ids), SalesOrder.tenant_id == tenant_id)
    result_orders = await db.execute(query_orders)
    sales_orders = result_orders.scalars().all()

    if not sales_orders:
        raise HTTPException(status_code=404, detail="Nenhum pedido encontrado.")

    addresses = ["Centro de Distribuição Base, São Paulo, SP"] # CD fixo como ponto 0

    for order in sales_orders:
        address = getattr(order, 'shipping_address', None)
        if not address:
            # Fallback mockado para evitar que a API do OSRM quebre se o endereço estiver vazio
            address = f"Rua {order.id}, São Paulo, SP" 
        addresses.append(address)

    try:
        # Chama o serviço de roteirização (Geopy -> OSRM -> OR-Tools)
        routing_result = await calculate_route(addresses)
        
        if "error" in routing_result:
            raise HTTPException(status_code=400, detail=routing_result["error"])
            
        # Mapeia a sequência otimizada (ignorando o índice 0 que é o depósito)
        optimized_sequence = []
        for seq_index in routing_result["sequence"]:
            if seq_index > 0 and seq_index <= len(sales_orders):
                # Subtrai 1 pois o índice 0 é o depósito, e a lista sales_orders começa em 0
                order_index = seq_index - 1
                optimized_sequence.append({
                    "order_id": str(sales_orders[order_index].id),
                    "optimized_position": len(optimized_sequence) + 1
                })
                
        return {
            "romaneio_id": romaneio_id,
            "optimized_orders": optimized_sequence,
            "total_distance_km": routing_result["total_distance_km"],
            "total_eta_minutes": routing_result["total_eta_minutes"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao otimizar rota: {str(e)}")