import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_product_success(client: AsyncClient):
    """
    Testa o fluxo feliz da criação de um produto (simulando um usuário logado).
    """
    payload = {
        "name": "Teclado Mecânico RGB",
        "sku": "TEC-RGB-001",
        "barcode": "7891234560011",
        "price": 350.00,
        "cost_price": 180.00,
        "min_stock": 5
    }
    
    response = await client.post("/products/", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Teclado Mecânico RGB"
    assert data["sku"] == "TEC-RGB-001"
    assert "id" in data
    assert data["current_stock"] == 0 # Estoque inicial padrão

@pytest.mark.asyncio
async def test_create_product_duplicate_sku(client: AsyncClient):
    """
    Testa a restrição de integridade (UniqueConstraint) no banco de dados.
    Dois produtos no mesmo tenant não podem ter o mesmo SKU.
    A API deve capturar a IntegrityError e devolver HTTP 400 em vez de 500.
    """
    payload = {
        "name": "Mouse Gamer",
        "sku": "MOUSE-001",
        "price": 150.00,
        "cost_price": 70.00,
    }
    
    # Primeira inserção: Sucesso
    res1 = await client.post("/products/", json=payload)
    assert res1.status_code == 201
    
    # Segunda inserção com o mesmo SKU: Falha tratada (HTTP 400)
    res2 = await client.post("/products/", json=payload)
    assert res2.status_code == 400
    assert "Já existe um produto com este SKU" in res2.json()["detail"]
