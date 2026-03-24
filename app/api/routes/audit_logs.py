from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import math

from app.core.deps import get_db, get_tenant_id
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogResponse, AuditLogPaginatedResponse

router = APIRouter()

@router.get("/", response_model=AuditLogPaginatedResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista os logs de auditoria do tenant atual com paginação e filtro por data.
    """
    # Base query
    base_query = select(AuditLog).where(AuditLog.tenant_id == tenant_id)

    # Aplica filtros de data se fornecidos
    if start_date:
        base_query = base_query.where(AuditLog.timestamp >= start_date)
    if end_date:
        # Garante que a data final cubra o dia inteiro (até 23:59:59.999999) 
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        base_query = base_query.where(AuditLog.timestamp <= end_date)

    # Total de itens
    count_query = select(func.count()).select_from(base_query.subquery())
    total_items = await db.scalar(count_query)

    # Paginação
    total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1
    skip = (page - 1) * per_page

    # Busca os itens
    query = base_query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(per_page)
    result = await db.execute(query)
    items = result.scalars().all()

    return AuditLogPaginatedResponse(
        items=items,
        total_items=total_items,
        total_pages=total_pages,
        current_page=page
    )
