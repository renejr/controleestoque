from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.help import HelpArticle, ChatbotLog
from app.schemas.help import HelpArticleCreate, HelpArticleResponse, ChatbotRequest, ChatbotResponse
from app.services.llm_service import generate_support_answer

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
    
    # 1. Busca todo o manual no banco (Para essa fase inicial, vamos concatenar tudo)
    # Num cenário real gigante, usaríamos busca vetorial com pgvector para trazer só os 3 artigos mais relevantes.
    query = select(HelpArticle)
    result = await db.execute(query)
    articles = result.scalars().all()
    
    if not articles:
        return ChatbotResponse(answer="Desculpe, o manual do sistema ainda não foi cadastrado. Contate o suporte.")

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
