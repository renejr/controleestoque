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
        query_prod = select(Product).where(Product.id == req_item.product_id, Product.tenant_id == tenant_id)
        result_prod = await db.execute(query_prod)
        product = result_prod.scalars().first()
        
        if not product:
            raise HTTPException(status_code=404, detail=f"Produto com ID {req_item.product_id} não encontrado.")
            
        # Valida se o produto possui as dimensões logísticas cadastradas (Fase 1 do projeto)
        # Assumindo que os campos logísticos do Product model sejam (weight, width, height, length) ou similares
        # Se os campos não existirem no Product model atual, usaremos um fallback temporário.
        try:
            # Tenta pegar as propriedades se existirem (depende de como o Product foi modelado na Fase 1)
            weight = float(getattr(product, 'weight', 0))
            width = float(getattr(product, 'width', 0))
            height = float(getattr(product, 'height', 0))
            length = float(getattr(product, 'length', 0))
        except AttributeError:
            # Fallback seguro caso os campos logísticos ainda não tenham sido injetados na Model Product
            weight = 0.0
            width = 0.0
            height = 0.0
            length = 0.0

        if weight <= 0 or width <= 0 or height <= 0 or length <= 0:
            raise HTTPException(
                status_code=400, 
                detail=f"O produto '{product.name}' não possui dimensões ou peso logístico válidos (> 0) cadastrados. Atualize o cadastro do produto primeiro."
            )

        # Desmembra a quantidade em unidades individuais para o algoritmo
        for _ in range(req_item.quantity):
            products_to_pack.append({
                "id": str(product.id),
                "name": product.name,
                "weight": weight,
                "width": width,
                "height": height,
                "length": length
            })

    # 3. Executa o Motor de Logística
    try:
        report = calculate_packing(vehicle, products_to_pack)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno no motor de logística: {str(e)}")

@router.post("/romaneio/{romaneio_id}/optimize", status_code=status.HTTP_200_OK)
async def optimize_romaneio_route(
    romaneio_id: str, # Can be UUID or string representing the Romaneio ID
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Otimiza a rota de entrega de um romaneio usando OSRM e OR-Tools.
    Retorna a sequência ideal, distância total real e tempo estimado (ETA).
    """
    
    # NOTA: Como não temos o modelo 'Romaneio' definido explicitamente no pedido, 
    # vamos assumir que o romaneio_id agrupa vários SalesOrders. 
    # Ou, em uma versão simplificada, vamos buscar SalesOrders com status específico para roteirização.
    
    # Busca os pedidos de venda (SalesOrders) que compõem o romaneio/rota
    # Substitua a cláusula where pela lógica real de agrupamento de romaneio do seu sistema
    # Por exemplo, se houver um campo romaneio_id no SalesOrder:
    query = select(SalesOrder).where(
        # SalesOrder.romaneio_id == romaneio_id, # Descomente se existir a relação
        SalesOrder.tenant_id == tenant_id,
        SalesOrder.status == "PROCESSING" # Apenas pedidos em separação
    ).limit(10) # Limite de segurança para a API OSRM
    
    result = await db.execute(query)
    sales_orders = result.scalars().all()
    
    if not sales_orders:
        raise HTTPException(status_code=404, detail="Nenhum pedido encontrado para otimização neste romaneio.")

    # Extrai os endereços dos pedidos
    # Precisamos do endereço do depósito (ponto de partida) como o primeiro item
    addresses = ["São Paulo, SP, Brasil"] # Ponto de partida (Depósito central) - Mockado para exemplo
    
    for order in sales_orders:
        # Assumindo que o SalesOrder ou Customer tenha o endereço de entrega
        # Se for necessário fazer um join com Customer, faça a query ajustada.
        # Aqui vamos usar um campo genérico ou mock se não existir
        # Ex: address = order.customer.address se o relacionamento existir
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
        raise HTTPException(status_code=500, detail=f"Erro interno no motor de roteirização: {str(e)}")
