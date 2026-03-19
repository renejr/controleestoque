import pytest
from typing import AsyncGenerator
from httpx import AsyncClient
from uuid import uuid4

from app.main import app
from app.core.database import engine, Base
from app.core.deps import get_db, get_current_user, get_tenant_id
from app.models.tenant import Tenant
from app.models.user import User

# Cria um Tenant ID fixo para os testes para facilitar o isolamento
TEST_TENANT_ID = uuid4()
TEST_USER_ID = uuid4()

# Mock do usuário atual para pular a autenticação JWT real nos testes de API
def override_get_current_user():
    return User(id=TEST_USER_ID, email="test@example.com", tenant_id=TEST_TENANT_ID)

def override_get_tenant_id():
    return TEST_TENANT_ID

@pytest.fixture(scope="session")
async def setup_db():
    # Cria as tabelas na base de dados de teste
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Limpa as tabelas após os testes
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def db_session(setup_db) -> AsyncGenerator:
    """
    Sessão transacional que faz rollback automático no final de cada teste,
    mantendo o banco de dados limpo.
    """
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.core.database import async_session_maker

    async with engine.connect() as conn:
        await conn.begin()
        async with async_session_maker(bind=conn) as session:
            
            # Garante que o Tenant de teste exista
            tenant = Tenant(id=TEST_TENANT_ID, name="Test Company", company_name="Test Company LTDA", document="00000000000100")
            session.add(tenant)
            await session.commit()
            
            yield session
        await conn.rollback()

@pytest.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """
    Cliente HTTP de teste com as dependências do FastAPI injetadas.
    """
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_tenant_id] = override_get_tenant_id
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
        
    app.dependency_overrides.clear()
