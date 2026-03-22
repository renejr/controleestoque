from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
import json

from app.core.deps import get_db, get_tenant_id
from app.models.vehicle import Vehicle
from app.models.product import Product
from app.models.sales_order import SalesOrder
from app.models.distribution_center import DistributionCenter
from app.schemas.fleet import PackOrderRequest
from app.services.logistics_service import calculate_packing  # <--- CORREÇÃO AQUI: Importando do arquivo certo!
from app.services.routing_service import calculate_route
from app.services.pdf_service import generate_manifest_pdf

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
                "name": product.name,
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
    vehicle_id: UUID,
    sales_orders_ids: list[UUID] = Query(...),
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query_orders = select(SalesOrder).where(SalesOrder.id.in_(sales_orders_ids), SalesOrder.tenant_id == tenant_id)
    result_orders = await db.execute(query_orders)
    sales_orders = result_orders.scalars().all()

    if not sales_orders:
        raise HTTPException(status_code=404, detail="Nenhum pedido encontrado.")

    # Busca o veículo e seu CD
    query_vehicle = select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.tenant_id == tenant_id)
    result_vehicle = await db.execute(query_vehicle)
    vehicle = result_vehicle.scalars().first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Veículo não encontrado.")
        
    ponto_zero = "Centro de Distribuição Base, São Paulo, SP" # Default fallback
    if vehicle.cd_id:
        query_cd = select(DistributionCenter).where(DistributionCenter.id == vehicle.cd_id, DistributionCenter.tenant_id == tenant_id)
        result_cd = await db.execute(query_cd)
        cd = result_cd.scalars().first()
        if cd:
            ponto_zero = f"{cd.address}, {cd.city}, {cd.state}, {cd.zip_code}"

    addresses = [ponto_zero] # Ponto 0 dinâmico

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

@router.post("/manifests/{romaneio_id}/pdf")
async def download_manifest_pdf(
    romaneio_id: str,
    payload: dict, # Recebe os dados de packing e routing via body temporariamente
    tenant_id: UUID = Depends(get_tenant_id)
):
    """
    Gera o PDF Tático de Romaneio com Planta Baixa e Checklist.
    """
    try:
        vehicle_data = payload.get("vehicle", {})
        manifest_data = payload.get("manifest", {})
        manifest_data['romaneio_id'] = romaneio_id
        
        pdf_bytes = generate_manifest_pdf(manifest_data, vehicle_data)
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=Romaneio_{romaneio_id}.pdf"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF: {str(e)}")