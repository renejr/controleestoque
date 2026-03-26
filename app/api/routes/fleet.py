from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
import json

from app.core.deps import get_db, get_tenant_id
from app.models.vehicle import Vehicle
from app.models.product import Product
from app.models.sales_order import SalesOrder
from app.models.sales_order_item import SalesOrderItem
from app.models.collection_order import CollectionOrder
from app.models.distribution_center import DistributionCenter
from app.models.tenant_setting import TenantSetting
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
    Suporta carregamento via múltiplos pedidos de venda (sales_orders_ids) ou lista manual de itens.
    """
    
    # 1. Busca o Veículo garantindo que pertence ao Tenant atual
    query_vehicle = select(Vehicle).where(Vehicle.id == request_data.vehicle_id, Vehicle.tenant_id == tenant_id)
    result_vehicle = await db.execute(query_vehicle)
    vehicle = result_vehicle.scalars().first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Veículo não encontrado ou não pertence à sua frota.")

    products_to_pack = []

    # Se recebeu lista de pedidos, extrai os itens deles
    if request_data.sales_orders_ids:
        # Carrega o relacionamento 'items' do SalesOrder, mas o SalesOrderItem não tem back_populates pro 'product' definido assim
        # Ele tem apenas product_id. Vamos buscar os produtos separados ou ajustar a query.
        # Já que não temos relationship('Product') no SalesOrderItem, vamos carregar só os items aqui e buscar produtos depois
        query_orders = select(SalesOrder).options(
            selectinload(SalesOrder.items)
        ).where(
            SalesOrder.id.in_(request_data.sales_orders_ids),
            SalesOrder.tenant_id == tenant_id
        )
        result_orders = await db.execute(query_orders)
        orders = result_orders.scalars().all()

        if not orders:
            raise HTTPException(status_code=404, detail="Nenhum pedido encontrado com os IDs fornecidos.")

        # Coleta os IDs de produtos necessários
        product_ids = set()
        for order in orders:
            for item in order.items:
                product_ids.add(item.product_id)
                
        # Busca todos os produtos de uma vez
        query_products = select(Product).where(Product.id.in_(product_ids), Product.tenant_id == tenant_id)
        result_products = await db.execute(query_products)
        products_dict = {p.id: p for p in result_products.scalars().all()}

        for order in orders:
            for item in order.items:
                product = products_dict.get(item.product_id)
                if not product:
                    continue
                    
                # Adiciona a quantidade de itens solicitada no pedido
                for _ in range(item.quantity):
                    products_to_pack.append({
                        "id": str(product.id),
                        "name": product.name,
                        "width": product.width,
                        "height": product.height,
                        "length": product.length,
                        "weight": product.weight
                    })

    # Fallback para itens manuais (se fornecidos no payload)
    elif request_data.items:
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
    else:
        raise HTTPException(status_code=400, detail="É necessário informar sales_orders_ids ou items.")

    if not products_to_pack:
         raise HTTPException(status_code=400, detail="Nenhum produto válido encontrado para cubagem.")

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
    query_orders = select(SalesOrder).options(selectinload(SalesOrder.customer)).where(SalesOrder.id.in_(sales_orders_ids), SalesOrder.tenant_id == tenant_id)
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
        # Tenta pegar o endereço do Customer
        address = None
        if hasattr(order, 'customer') and order.customer:
            c = order.customer
            # Formato rigoroso para o geopy/nominatim achar mais fácil
            address = f"{c.street}, {c.number}, {c.city}, {c.state}, {c.zip_code}, Brazil"
        
        if not address or address.strip() == ", , , , , Brazil":
            # Fallback mockado para evitar que a API do OSRM quebre se o endereço estiver vazio
            # Vamos usar um endereço válido no Centro de SP para fallback
            address = f"Praça da Sé, São Paulo, SP, 01001-000, Brazil" 
        addresses.append(address)

    try:
        # Chama o serviço de roteirização (Geopy -> OSRM -> OR-Tools)
        routing_result = await calculate_route(addresses)
        
        if "error" in routing_result:
            raise HTTPException(status_code=400, detail=routing_result["error"])
            
        # Mapeia a sequência otimizada (ignorando o índice 0 que é o depósito) e inclui coordenadas
        optimized_sequence = []
        sequence = routing_result["sequence"]
        sequence_coords = routing_result.get("sequence_coordinates", [])
        for i, seq_index in enumerate(sequence):
            if seq_index > 0 and seq_index <= len(sales_orders):
                order_index = seq_index - 1
                lat, lng = (0.0, 0.0)
                if i < len(sequence_coords):
                    lat, lng = sequence_coords[i]
                optimized_sequence.append({
                    "order_id": str(sales_orders[order_index].id),
                    "optimized_position": len(optimized_sequence) + 1,
                    "lat": lat,
                    "lng": lng
                })
                
        return {
            "romaneio_id": romaneio_id,
            "optimized_orders": optimized_sequence,
            "total_distance_km": routing_result["total_distance_km"],
            "total_eta_minutes": routing_result["total_eta_minutes"],
            "geometry": routing_result.get("geometry", {}),
            "steps": routing_result.get("steps", [])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao otimizar rota: {str(e)}")

from pydantic import BaseModel
from typing import List, Optional

class MixedRouteRequest(BaseModel):
    vehicle_id: UUID
    sales_orders_ids: List[UUID] = []
    collection_orders_ids: List[UUID] = []

@router.post("/optimize-mixed-route", status_code=status.HTTP_200_OK)
async def optimize_mixed_route(
    request: MixedRouteRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    if not request.sales_orders_ids and not request.collection_orders_ids:
        raise HTTPException(status_code=400, detail="Nenhum pedido de venda ou coleta fornecido.")

    # Busca o veículo e seu CD
    query_vehicle = select(Vehicle).where(Vehicle.id == request.vehicle_id, Vehicle.tenant_id == tenant_id)
    result_vehicle = await db.execute(query_vehicle)
    vehicle = result_vehicle.scalars().first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Veículo não encontrado.")
        
    ponto_zero = "Praça da Sé, São Paulo, SP, 01001-000, Brazil" # Default fallback
    if vehicle.cd_id:
        query_cd = select(DistributionCenter).where(DistributionCenter.id == vehicle.cd_id, DistributionCenter.tenant_id == tenant_id)
        result_cd = await db.execute(query_cd)
        cd = result_cd.scalars().first()
        if cd:
            ponto_zero = f"{cd.address}, {cd.city}, {cd.state}, {cd.zip_code}"

    addresses = [ponto_zero]
    stops_info = [] # Store metadata for mapping back the results

    # 1. Process Sales Orders (Deliveries)
    if request.sales_orders_ids:
        query_sales = select(SalesOrder).options(selectinload(SalesOrder.customer)).where(
            SalesOrder.id.in_(request.sales_orders_ids), 
            SalesOrder.tenant_id == tenant_id
        )
        result_sales = await db.execute(query_sales)
        sales_orders = result_sales.scalars().all()
        
        for order in sales_orders:
            address = None
            if hasattr(order, 'customer') and order.customer:
                c = order.customer
                address = f"{c.street}, {c.number}, {c.city}, {c.state}, {c.zip_code}, Brazil"
            
            if not address or address.strip() == ", , , , , Brazil":
                address = "Praça da Sé, São Paulo, SP, 01001-000, Brazil"
                
            addresses.append(address)
            stops_info.append({
                "id": str(order.id),
                "type": "DELIVERY",
                "name": order.customer.name if order.customer else "Cliente Desconhecido"
            })

    # 2. Process Collection Orders
    if request.collection_orders_ids:
        query_collections = select(CollectionOrder).where(
            CollectionOrder.id.in_(request.collection_orders_ids),
            CollectionOrder.tenant_id == tenant_id
        )
        result_collections = await db.execute(query_collections)
        collection_orders = result_collections.scalars().all()
        
        for order in collection_orders:
            address = order.pickup_address
            if not address or len(address.strip()) < 5:
                address = "Praça da Sé, São Paulo, SP, 01001-000, Brazil"
                
            addresses.append(address)
            stops_info.append({
                "id": str(order.id),
                "type": "COLLECTION",
                "name": order.sender_name
            })

    try:
        # Chama o serviço de roteirização (Geopy -> OSRM -> OR-Tools)
        routing_result = await calculate_route(addresses)
        
        if "error" in routing_result:
            raise HTTPException(status_code=400, detail=routing_result["error"])
            
        optimized_sequence = []
        sequence = routing_result["sequence"]
        sequence_coords = routing_result.get("sequence_coordinates", [])
        
        for i, seq_index in enumerate(sequence):
            # seq_index 0 is the depot
            if seq_index > 0 and seq_index <= len(stops_info):
                stop_meta = stops_info[seq_index - 1]
                lat, lng = (0.0, 0.0)
                if i < len(sequence_coords):
                    lat, lng = sequence_coords[i]
                    
                optimized_sequence.append({
                    "order_id": stop_meta["id"],
                    "type": stop_meta["type"],
                    "name": stop_meta["name"],
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
        raise HTTPException(status_code=500, detail=f"Erro interno na roteirização mista: {str(e)}")

@router.post("/manifests/{romaneio_id}/pdf")
async def download_manifest_pdf(
    romaneio_id: str,
    payload: dict, # Recebe os dados de packing e routing via body temporariamente
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Gera o PDF Tático de Romaneio com Planta Baixa e Checklist.
    """
    try:
        # Busca as configurações do tenant para branding
        query_settings = select(TenantSetting).where(TenantSetting.tenant_id == tenant_id)
        result_settings = await db.execute(query_settings)
        settings = result_settings.scalars().first()
        
        tenant_settings_dict = {}
        if settings:
            tenant_settings_dict = {
                'company_name': settings.company_name,
                'logo_url': settings.logo_url
            }

        vehicle_data = payload.get("vehicle", {})
        manifest_data = payload.get("manifest", {})
        manifest_data['romaneio_id'] = romaneio_id
        
        pdf_bytes = generate_manifest_pdf(manifest_data, vehicle_data, tenant_settings_dict)
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=Romaneio_{romaneio_id}.pdf"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF: {str(e)}")
