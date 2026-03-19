import asyncio
import sys
import os

# Adiciona o diretório raiz ao PYTHONPATH para importar os módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import SessionLocal
from app.models.tenant import Tenant
from app.models.user import User
from app.core.security import get_password_hash

async def seed():
    async with SessionLocal() as db:
        print("🌱 Iniciando o Seed...")

        # 1. Verifica se já existe um tenant
        result = await db.execute(select(Tenant).where(Tenant.name == "Empresa Teste"))
        existing_tenant = result.scalars().first()

        if not existing_tenant:
            print("🏢 Criando Tenant 'Empresa Teste'...")
            tenant = Tenant(name="Empresa Teste")
            db.add(tenant)
            await db.commit()
            await db.refresh(tenant)
        else:
            print("🏢 Tenant 'Empresa Teste' já existe.")
            tenant = existing_tenant

        # 2. Verifica se já existe o usuário admin
        result = await db.execute(select(User).where(User.email == "admin@teste.com"))
        existing_user = result.scalars().first()

        if not existing_user:
            print("👤 Criando Usuário 'admin@teste.com'...")
            user = User(
                tenant_id=tenant.id,
                name="Administrador",
                email="admin@teste.com",
                hashed_password=get_password_hash("123456"),
                role="admin"
            )
            db.add(user)
            await db.commit()
            print("✅ Usuário criado com sucesso!")
        else:
            print("👤 Usuário 'admin@teste.com' já existe.")

        print("🎉 Seed concluído!")

if __name__ == "__main__":
    asyncio.run(seed())
