from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.help import HelpArticle, ChatbotLog
from app.schemas.help import HelpArticleCreate, HelpArticleResponse, ChatbotRequest, ChatbotResponse, ChatbotLogResponse
from app.services.llm_service import generate_support_answer, get_embedding

router = APIRouter(prefix="/help", tags=["Help & Support"])

@router.get("/articles", response_model=List[HelpArticleResponse])
async def list_help_articles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retorna o manual do sistema (visível para todos os tenants).
    """
    query = select(HelpArticle).order_by(HelpArticle.category, HelpArticle.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/articles", response_model=HelpArticleResponse, status_code=status.HTTP_201_CREATED)
async def create_help_article(
    article_in: HelpArticleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cria um novo artigo no manual.
    (Opcional: você poderia travar para apenas Super Admins no futuro)
    """
    if current_user.role != "ADMIN":
        # Assumindo que os admins do SaaS podem contribuir com a base de conhecimento.
        # Caso queira que apenas donos do código alterem, proteja com API_KEY.
        raise HTTPException(status_code=403, detail="Sem permissão para criar artigos.")

    new_article = HelpArticle(
        title=article_in.title,
        content=article_in.content,
        category=article_in.category
    )
    db.add(new_article)
    await db.commit()
    await db.refresh(new_article)
    return new_article

@router.post("/ask-bot", response_model=ChatbotResponse)
async def ask_chatbot(
    request: ChatbotRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Envia a pergunta para o LLM responder com base no manual do sistema.
    Salva o log da conversa para auditoria de retenção.
    """
    
    # 1. Gera o embedding da pergunta do usuário
    question_embedding = await get_embedding(request.message)
    
    if not question_embedding:
        return ChatbotResponse(answer="Desculpe, ocorreu um erro ao processar a semântica da sua pergunta. Tente novamente.")

    # 2. Busca os 3 artigos mais relevantes no banco usando pgvector (cosine distance)
    # distance < 0.5 garante que não vamos trazer artigos completamente aleatórios
    query = (
        select(HelpArticle)
        .where(HelpArticle.embedding.cosine_distance(question_embedding) < 0.6)
        .order_by(HelpArticle.embedding.cosine_distance(question_embedding))
        .limit(3)
    )
    result = await db.execute(query)
    articles = result.scalars().all()
    
    if not articles:
        # Se não achou nada relevante, nem chama o LLM para evitar alucinação
        return ChatbotResponse(answer="Desculpe, não encontrei essa informação no manual. Por favor, contate nosso suporte humano através da aba de Ajuda.")

    # 2. Monta o contexto agregando o texto
    context_parts = []
    for art in articles:
        context_parts.append(f"TÍTULO: {art.title}\nCONTEÚDO: {art.content}")
    
    context_text = "\n\n".join(context_parts)
    
    # 3. Chama o LLM
    bot_answer = await generate_support_answer(
        question=request.message,
        context_text=context_text
    )
    
    # 4. Salva a auditoria da conversa
    log_entry = ChatbotLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        user_message=request.message,
        bot_response=bot_answer
    )
    db.add(log_entry)
    await db.commit()
    
    # 5. Retorna para o Frontend
    return ChatbotResponse(answer=bot_answer)

@router.get("/ask-bot/history", response_model=List[ChatbotLogResponse])
async def get_chatbot_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retorna o histórico de conversas do usuário atual com o bot de ajuda.
    """
    query = (
        select(ChatbotLog)
        .where(
            ChatbotLog.tenant_id == current_user.tenant_id,
            ChatbotLog.user_id == current_user.id
        )
        .order_by(ChatbotLog.created_at.asc())
    )
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return [
        ChatbotLogResponse(
            id=str(log.id),
            user_message=log.user_message,
            bot_response=log.bot_response,
            created_at=log.created_at
        ) for log in logs
    ]
