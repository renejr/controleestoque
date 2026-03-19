import pytest
from httpx import AsyncClient
from uuid import uuid4

async def _setup_vehicle_and_product(client: AsyncClient, db_session, vehicle_capacity: float, product_weight: float, p_width: float, p_height: float, p_length: float):
    """
    Cria um veículo e um produto (com dimensões forçadas no banco) para simular o Bin Packing.
    """
    from app.models.product import Product
    from sqlalchemy import select

    # 1. Cria Veículo
    v_payload = {
        "license_plate": f"ABC{uuid4().hex[:4]}",
        "model_name": "Caminhão Teste",
        "tare_weight": 2000,
        "max_weight_capacity": vehicle_capacity,
        "max_volume_capacity": 15.0, # m3
        "compartment_width": 200,    # cm
        "compartment_height": 200,   # cm
        "compartment_length": 400    # cm
    }
    res_v = await client.post("/vehicles/", json=v_payload)
    vehicle_id = res_v.json()["id"]

    # 2. Cria Produto
    p_payload = {
        "name": "Caixa Teste",
        "sku": f"CX-{uuid4().hex[:6]}",
        "price": 100,
        "cost_price": 50,
    }
    res_p = await client.post("/products/", json=p_payload)
    product_id = res_p.json()["id"]

    # 3. Força as dimensões logísticas no banco (como a rota de Produto não tem os campos no schema ainda, injetamos direto)
    query = select(Product).where(Product.id == product_id)
    result = await db_session.execute(query)
    product = result.scalars().first()
    product.weight = product_weight
    product.width = p_width
    product.height = p_height
    product.length = p_length
    await db_session.commit()

    return vehicle_id, product_id


@pytest.mark.asyncio
async def test_pack_order_success(client: AsyncClient, db_session):
    """
    Testa um caminhão gigante com caixas pequenas. Todas devem caber (unfitted = 0).
    """
    # Caminhão suporta 5000kg. Produto pesa 10kg e tem 50x50x50 cm
    v_id, p_id = await _setup_vehicle_and_product(
        client, db_session, 
        vehicle_capacity=5000.0, 
        product_weight=10.0, 
        p_width=50.0, p_height=50.0, p_length=50.0
    )

    payload = {
        "vehicle_id": v_id,
        "items": [
            {"product_id": p_id, "quantity": 10} # 10 caixas
        ]
    }

    response = await client.post("/fleet/pack-order", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["fitted_items_count"] == 10
    assert data["unfitted_items_count"] == 0
    assert len(data["fitted_items"]) == 10
    
    # Verifica se as coordenadas existem
    first_item = data["fitted_items"][0]
    assert "position" in first_item
    assert "x" in first_item["position"]


@pytest.mark.asyncio
async def test_pack_order_overflow(client: AsyncClient, db_session):
    """
    Testa um caminhão pequeno sendo sobrecarregado. Alguns itens devem ficar de fora.
    """
    # Caminhão suporta apenas 100kg. Produto pesa 30kg.
    v_id, p_id = await _setup_vehicle_and_product(
        client, db_session, 
        vehicle_capacity=100.0, 
        product_weight=30.0, 
        p_width=50.0, p_height=50.0, p_length=50.0
    )

    # Tenta enviar 5 caixas (30kg * 5 = 150kg). O caminhão só aguenta 100kg.
    payload = {
        "vehicle_id": v_id,
        "items": [
            {"product_id": p_id, "quantity": 5}
        ]
    }

    response = await client.post("/fleet/pack-order", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    # 3 caixas de 30kg = 90kg (cabem). A 4ª caixa faria dar 120kg, estourando os 100kg.
    # Portanto, 3 devem caber e 2 devem sobrar.
    assert data["fitted_items_count"] == 3
    assert data["unfitted_items_count"] == 2
    assert data["metrics"]["total_weight_used_kg"] == 90.0
    assert data["metrics"]["weight_utilization_percent"] == 90.0 # 90/100
