from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.deps import get_db, get_tenant_id
from app.models.vehicle import Vehicle
from app.models.product import Product
from app.schemas.fleet import PackOrderRequest
from app.services.logistics_service import calculate_packing

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
