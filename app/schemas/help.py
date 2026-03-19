from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime

# --- Help Article Schemas ---

class HelpArticleBase(BaseModel):
    title: str = Field(..., description="Título do artigo de ajuda")
    content: str = Field(..., description="Conteúdo completo do artigo")
    category: str = Field(..., description="Categoria (ex: ESTOQUE, FINANCEIRO, GERAL)")

class HelpArticleCreate(HelpArticleBase):
    pass

class HelpArticleResponse(HelpArticleBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Chatbot Schemas ---

class ChatbotRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Pergunta do usuário para a IA")

class ChatbotResponse(BaseModel):
    answer: str = Field(..., description="Resposta gerada pela IA")
