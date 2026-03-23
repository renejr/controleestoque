import json
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
import jwt
from jwt.exceptions import PyJWTError

from app.core.database import SessionLocal
from app.core.config import settings
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.message import ChatMessage
from app.schemas.message import ChatMessageResponse
from app.services.chat_manager import manager

router = APIRouter(tags=["Chat"])

@router.get("/chat/history/{contact_id}", response_model=List[ChatMessageResponse])
async def get_chat_history(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retorna o histórico de mensagens entre o usuário logado e um contato específico.
    """
    # Verifica se o contato existe no mesmo tenant
    contact_query = select(User).where(User.id == contact_id, User.tenant_id == current_user.tenant_id)
    contact_result = await db.execute(contact_query)
    contact = contact_result.scalars().first()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contato não encontrado.")

    # Busca as mensagens (enviadas por mim para ele, ou por ele para mim)
    query = select(ChatMessage).where(
        ChatMessage.tenant_id == current_user.tenant_id,
        or_(
            and_(ChatMessage.sender_id == current_user.id, ChatMessage.receiver_id == contact_id),
            and_(ChatMessage.sender_id == contact_id, ChatMessage.receiver_id == current_user.id)
        )
    ).order_by(ChatMessage.created_at.asc())
    
    result = await db.execute(query)
    messages = result.scalars().all()
    
    # Formata a resposta
    response = []
    for msg in messages:
        sender_name = current_user.name if msg.sender_id == current_user.id else contact.name
        receiver_name = contact.name if msg.receiver_id == contact.id else current_user.name
        
        response.append(
            ChatMessageResponse(
                id=msg.id,
                tenant_id=msg.tenant_id,
                sender_id=msg.sender_id,
                receiver_id=msg.receiver_id,
                content=msg.content,
                is_read=msg.is_read,
                created_at=msg.created_at,
                sender_name=sender_name,
                receiver_name=receiver_name
            )
        )
        
    return response

@router.websocket("/ws/chat/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """
    Endpoint de WebSocket para o Chat em Tempo Real.
    """
    # 1. ACEITAÇÃO PRIMEIRO: O FastAPI precisa aceitar o handshake antes de processar.
    await websocket.accept()

    # 2. Autenticação via Token
    try:
        # Remover o prefixo 'Bearer ' se o Flutter estiver enviando por engano na URL
        clean_token = token.replace("Bearer ", "") if token.startswith("Bearer ") else token
        
        payload = jwt.decode(clean_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        
        if user_id is None or tenant_id is None:
            print("❌ [WebSocket] Conexão Rejeitada: 'sub' ou 'tenant_id' ausentes no token.")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
            
    except PyJWTError as e:
        print(f"❌ [WebSocket] Conexão Rejeitada: Falha na validação do JWT. Motivo: {str(e)}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    except Exception as e:
        print(f"❌ [WebSocket] Erro inesperado na autenticação: {str(e)}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    # 3. Conexão Segura
    print(f"✅ [WebSocket] Usuário {user_id} autenticado com sucesso.")
    
    # ATENÇÃO AGENTE: Certifique-se de que a função manager.connect() não está chamando
    # 'await websocket.accept()' novamente, pois já fizemos isso acima.
    await manager.connect(websocket, tenant_id, user_id)
    
    db: AsyncSession = SessionLocal()

    try:
        # Loop de recebimento de mensagens
        while True:
            data_text = await websocket.receive_text()
            data = json.loads(data_text)
            
            if data.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue
            
            receiver_id = data.get("receiver_id")
            content = data.get("content")
            
            if receiver_id and content:
                new_message = ChatMessage(
                    tenant_id=UUID(tenant_id),
                    sender_id=UUID(user_id),
                    receiver_id=UUID(receiver_id),
                    content=content
                )
                db.add(new_message)
                await db.commit()
                await db.refresh(new_message)
                
                message_payload = {
                    "id": str(new_message.id),
                    "sender_id": user_id,
                    "receiver_id": receiver_id,
                    "content": content,
                    "created_at": new_message.created_at.isoformat()
                }
                
                await manager.send_personal_message(message_payload, tenant_id, receiver_id)
                
    except WebSocketDisconnect:
        print(f"⚠️ [WebSocket] Usuário {user_id} desconectado.")
        manager.disconnect(tenant_id, user_id)
    finally:
        await db.close()
