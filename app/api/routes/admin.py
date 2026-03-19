from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.deps import get_db
from app.core.security import verify_api_key
from app.models.audit_log import AuditLog
from app.models.tenant import Tenant
from app.models.suggestion import Suggestion
from app.models.user import User
from app.schemas.audit_log import SuperAdminAuditLogResponse
from app.schemas.suggestion import SuperAdminSuggestionResponse, SuggestionStatusUpdate

router = APIRouter(prefix="/admin", tags=["Super Admin"])

@router.get("/audit-logs", response_model=List[SuperAdminAuditLogResponse])
async def get_all_audit_logs(
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db)
):
    """
    Retorna os últimos 200 logs de auditoria globais do sistema.
    Protegido APENAS por API KEY (Server-to-Server).
    Cruza com a tabela Tenant para retornar o nome da empresa afetada.
    """
    
    # Realiza um JOIN para buscar o AuditLog junto com as informações do Tenant
    query = (
        select(AuditLog, Tenant.name.label("tenant_name"))
        .join(Tenant, AuditLog.tenant_id == Tenant.id)
        .order_by(AuditLog.timestamp.desc())
        .limit(200)
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    # Monta a resposta formatada
    response_list = []
    for log, tenant_name in rows:
        response_list.append(
            SuperAdminAuditLogResponse(
                id=log.id,
                tenant_id=log.tenant_id,
                user_id=log.user_id,
                action=log.action,
                table_name=log.table_name,
                record_id=log.record_id,
                old_data=log.old_data,
                new_data=log.new_data,
                timestamp=log.timestamp,
                tenant_name=tenant_name
            )
        )
        
    return response_list

@router.patch("/suggestions/{suggestion_id}/status", response_model=SuperAdminSuggestionResponse)
async def update_suggestion_status(
    suggestion_id: UUID,
    payload: SuggestionStatusUpdate,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db)
):
    """
    Atualiza o status de uma sugestão globalmente.
    Protegido APENAS por API KEY.
    """
    # Busca a sugestão original cruzando com Tenant e User para devolver a resposta formatada
    query = (
        select(
            Suggestion,
            Tenant.name.label("tenant_name"),
            User.name.label("user_name"),
            User.email.label("user_email")
        )
        .join(Tenant, Suggestion.tenant_id == Tenant.id)
        .join(User, Suggestion.user_id == User.id)
        .where(Suggestion.id == suggestion_id)
    )
    
    result = await db.execute(query)
    row = result.first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Sugestão não encontrada")
        
    suggestion, tenant_name, user_name, user_email = row
    
    # Atualiza o status
    suggestion.status = payload.status
    await db.commit()
    await db.refresh(suggestion)
    
    display_name = user_name if user_name else user_email
    
    return SuperAdminSuggestionResponse(
        id=suggestion.id,
        tenant_id=suggestion.tenant_id,
        user_id=suggestion.user_id,
        title=suggestion.title,
        description=suggestion.description,
        status=suggestion.status,
        created_at=suggestion.created_at,
        tenant_name=tenant_name,
        user_name=display_name
    )

@router.get("/suggestions", response_model=List[SuperAdminSuggestionResponse])
async def get_all_suggestions(
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db)
):
    """
    Retorna as sugestões globais de todos os tenants.
    Protegido APENAS por API KEY (Server-to-Server).
    Cruza com as tabelas Tenant e User para retornar os nomes.
    """
    query = (
        select(
            Suggestion,
            Tenant.name.label("tenant_name"),
            User.name.label("user_name"),
            User.email.label("user_email")
        )
        .join(Tenant, Suggestion.tenant_id == Tenant.id)
        .join(User, Suggestion.user_id == User.id)
        .order_by(Suggestion.created_at.desc())
        .limit(200)
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    response_list = []
    for suggestion, tenant_name, user_name, user_email in rows:
        # Fallback para o email caso o usuário não tenha cadastrado nome
        display_name = user_name if user_name else user_email
        
        response_list.append(
            SuperAdminSuggestionResponse(
                id=suggestion.id,
                tenant_id=suggestion.tenant_id,
                user_id=suggestion.user_id,
                title=suggestion.title,
                description=suggestion.description,
                status=suggestion.status,
                created_at=suggestion.created_at,
                tenant_name=tenant_name,
                user_name=display_name
            )
        )
        
    return response_list
