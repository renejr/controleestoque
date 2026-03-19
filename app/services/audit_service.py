from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog
from uuid import UUID
from typing import Optional, Any
import json
from decimal import Decimal
from datetime import datetime

class CustomJSONEncoder(json.JSONEncoder):
    """Encoder customizado para lidar com tipos não serializáveis pelo json padrão."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

async def log_audit_event(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: Optional[UUID],
    action: str,
    table_name: str,
    record_id: str,
    old_data: Optional[dict] = None,
    new_data: Optional[dict] = None
):
    """
    Registra um evento de auditoria no banco de dados.
    """
    
    # Prepara os dados serializando com o encoder customizado para lidar com Decimals e UUIDs
    safe_old_data = json.loads(json.dumps(old_data, cls=CustomJSONEncoder)) if old_data else None
    safe_new_data = json.loads(json.dumps(new_data, cls=CustomJSONEncoder)) if new_data else None

    audit_log = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        table_name=table_name,
        record_id=str(record_id),
        old_data=safe_old_data,
        new_data=safe_new_data
    )
    
    db.add(audit_log)
    # Não chamamos commit aqui. O commit deve ser feito pelo chamador
    # para garantir que a auditoria e a alteração principal ocorram na mesma transação.
