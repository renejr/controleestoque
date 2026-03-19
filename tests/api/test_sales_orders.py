import pytest
from httpx import AsyncClient
from uuid import uuid4

async def _setup_data_for_sales(client: AsyncClient):
    """
    Função auxiliar para criar um cliente e um produto com estoque 
    para serem usados nos testes de vendas.
    """
    # 1. Cria o Cliente
    customer_payload = {
        "name": "João da Silva",
        "document": "12345678900"
    }
    res_customer = await client.post("/customers/", json=customer_payload)
    customer_id = res_customer.json()["id"]
    
    # 2. Cria o Produto
    product_payload = {
        "name": "Smartphone XYZ",
        "sku": f"PHONE-{uuid4().hex[:6]}", # SKU dinâmico para não dar conflito com outros testes
        "price": 2000.00,
        "cost_price": 1000.00,
    }
    res_product = await client.post("/products/", json=product_payload)
    product_id = res_product.json()["id"]
    
    # 3. Dá entrada manual no estoque do produto (usando a rota de compras/transações seria o ideal,
    # mas para isolamento do teste, vamos assumir que o banco foi manipulado ou usar uma rota interna se existisse.
    # Como não temos uma rota direta para injetar estoque livremente, 
    # vamos manipular via banco de dados usando a fixture do db se precisarmos de muito estoque.
    # No FastAPI a gente testará a lógica simulando a injeção via código.
    
    return customer_id, product_id


@pytest.mark.asyncio
async def test_create_sales_order(client: AsyncClient):
    """
    Simula a criação de um pedido de venda (DRAFT) com cliente e produtos válidos.
    """
    customer_id, product_id = await _setup_data_for_sales(client)
    
    order_payload = {
        "customer_id": customer_id,
        "notes": "Pedido de Teste",
        "items": [
            {
                "product_id": product_id,
                "quantity": 2,
                "unit_price": 2000.00
            }
        ]
    }
    
    response = await client.post("/sales-orders/", json=order_payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "DRAFT"
    assert data["total_amount"] == 4000.00 # 2 * 2000
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_sales_order_shipped_trigger_success(client: AsyncClient, db_session):
    """
    Verifica se mudar o status para SHIPPED diminui o estoque do produto.
    """
    # Usaremos db_session para forçar um estoque inicial diretamente no banco
    # já que a rota de criação de produto inicia com 0.
    from app.models.product import Product
    from sqlalchemy import select
    
    customer_id, product_id = await _setup_data_for_sales(client)
    
    # Força 10 unidades no estoque diretamente no banco
    query = select(Product).where(Product.id == product_id)
    result = await db_session.execute(query)
    product = result.scalars().first()
    product.current_stock = 10
    await db_session.commit()
    
    # Cria o Pedido (vendendo 3 unidades)
    order_payload = {
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 3, "unit_price": 2000.00}]
    }
    res_order = await client.post("/sales-orders/", json=order_payload)
    order_id = res_order.json()["id"]
    
    # Muda o Status para SHIPPED
    res_ship = await client.patch(f"/sales-orders/{order_id}/status", json={"status": "SHIPPED"})
    
    assert res_ship.status_code == 200
    assert res_ship.json()["status"] == "SHIPPED"
    
    # Verifica no banco se o estoque caiu de 10 para 7
    await db_session.refresh(product)
    assert product.current_stock == 7


@pytest.mark.asyncio
async def test_sales_order_shipped_insufficient_stock(client: AsyncClient, db_session):
    """
    Tenta enviar um pedido onde a quantidade vendida é maior que o estoque.
    """
    from app.models.product import Product
    from sqlalchemy import select
    
    customer_id, product_id = await _setup_data_for_sales(client)
    
    # Força 2 unidades no estoque
    query = select(Product).where(Product.id == product_id)
    result = await db_session.execute(query)
    product = result.scalars().first()
    product.current_stock = 2
    await db_session.commit()
    
    # Cria o Pedido (tentando vender 5 unidades)
    order_payload = {
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 5, "unit_price": 2000.00}]
    }
    res_order = await client.post("/sales-orders/", json=order_payload)
    order_id = res_order.json()["id"]
    
    # Tenta mudar o Status para SHIPPED
    res_ship = await client.patch(f"/sales-orders/{order_id}/status", json={"status": "SHIPPED"})
    
    # O backend deve bloquear com erro 400
    assert res_ship.status_code == 400
    assert "Estoque insuficiente" in res_ship.json()["detail"]
    
    # O estoque deve continuar intacto (2)
    await db_session.refresh(product)
    assert product.current_stock == 2
