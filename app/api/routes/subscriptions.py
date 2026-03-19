import secrets
import string
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.deps import get_db
from app.core.security import verify_api_key, get_password_hash
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.subscription import TenantProvisionRequest, TenantProvisionResponse

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions / Webhooks"])

def generate_random_password(length=12):
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))

@router.post("/provision-tenant", response_model=TenantProvisionResponse, status_code=status.HTTP_201_CREATED)
async def provision_tenant(
    payload: TenantProvisionRequest,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db)
):
    """
    Webhook para criar um Tenant e seu Usuário Admin automaticamente após uma venda aprovada.
    Protegido por API_KEY estática (Não usa JWT).
    Operação atômica: Ou cria ambos (Tenant e Admin), ou falha tudo (Rollback).
    """
    
    # 1. Verifica se o e-mail já existe globalmente
    query_email = select(User).where(User.email == payload.admin_email)
    result_email = await db.execute(query_email)
    if result_email.scalars().first():
        raise HTTPException(status_code=400, detail="Este e-mail já está cadastrado em nossa base.")

    # 2. Verifica se o CNPJ/Documento já existe globalmente (se fornecido)
    if payload.document:
        query_doc = select(Tenant).where(Tenant.cnpj == payload.document)
        result_doc = await db.execute(query_doc)
        if result_doc.scalars().first():
            raise HTTPException(status_code=400, detail="Este documento já está registrado em nossa base.")

    # Transação Atômica começa implicitamente no get_db()
    try:
        # 3. Cria o Tenant (Empresa)
        new_tenant = Tenant(
            name=payload.company_name,
            cnpj=payload.document,
            # Salvamos o plan_type no tax_regime provisoriamente, 
            # ou você pode criar um campo 'plan_type' real depois
        )
        db.add(new_tenant)
        await db.flush() # Dispara para o banco para gerar o ID do Tenant, sem commitar a transação

        # 4. Resolve a Senha
        password_to_hash = payload.admin_password if payload.admin_password else generate_random_password()

        # 5. Cria o Usuário Admin
        new_admin = User(
            tenant_id=new_tenant.id,
            name=payload.admin_name,
            email=payload.admin_email,
            hashed_password=get_password_hash(password_to_hash),
            role="ADMIN",
            is_active=True
        )
        db.add(new_admin)
        
        # Se tudo deu certo até aqui, commita a transação
        await db.commit()
        await db.refresh(new_tenant)
        await db.refresh(new_admin)

        # TODO: Se payload.admin_password era None, disparar e-mail com password_to_hash para o cliente aqui.

        return TenantProvisionResponse(
            tenant_id=str(new_tenant.id),
            admin_id=str(new_admin.id),
            company_name=new_tenant.name,
            admin_email=new_admin.email
        )

    except Exception as e:
        # Se algo falhar (ex: queda de conexão no meio da criação do usuário),
        # o rollback desfaz a criação do Tenant que aconteceu no flush()
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro interno ao provisionar ambiente: {str(e)}")
