import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_tenant_me(client: AsyncClient):
    """
    Verifica se a rota devolve os dados fiscais corretamente do tenant mockado.
    """
    response = await client.get("/tenants/me")
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Company"
    assert data["company_name"] == "Test Company LTDA"
    assert data["document"] == "00000000000100"

@pytest.mark.asyncio
async def test_update_tenant_me(client: AsyncClient):
    """
    Verifica se a atualização de campos fiscais (Regime Tributário) funciona perfeitamente.
    """
    update_payload = {
        "company_name": "Test Company S.A.",
        "tax_regime": "LUCRO_REAL"
    }
    
    response = await client.put("/tenants/me", json=update_payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["company_name"] == "Test Company S.A."
    assert data["tax_regime"] == "LUCRO_REAL"
    # O CNPJ deve continuar intacto
    assert data["document"] == "00000000000100"
