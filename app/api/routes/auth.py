from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import jwt
from datetime import timedelta

from app.core.deps import get_db
from app.core.security import verify_password, create_access_token, get_password_hash
from app.core.config import settings
from app.models.user import User

router = APIRouter()

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint de login (OAuth2 standard).
    Valida email e senha, retornando um JWT Access Token.
    """
    # Busca o usuário pelo email
    query = select(User).where(User.email == form_data.username)
    result = await db.execute(query)
    user = result.scalars().first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Cria o token incluindo user_id e tenant_id
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "tenant_id": str(user.tenant_id),
            "role": user.role
        }
    )

    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Gera um token de recuperação de senha.
    Como não há SMTP, retorna o token no JSON para testes no Frontend.
    """
    query = select(User).where(User.email == request.email)
    result = await db.execute(query)
    user = result.scalars().first()

    if not user:
        # Por segurança, retornamos a mesma mensagem de sucesso
        # para evitar enumeramento de e-mails, mas geramos erro interno (ou ignoramos).
        # Para facilitar o MOCK de DEV, se o email não existir, damos erro 404 para feedback visual.
        raise HTTPException(status_code=404, detail="Email não encontrado.")

    # Cria um token JWT válido por 15 minutos
    reset_token = create_access_token(
        data={"sub": str(user.id), "type": "reset_password"},
        expires_delta=timedelta(minutes=15)
    )

    return {
        "message": "Instruções enviadas para o seu e-mail.",
        "dev_mock_token": reset_token
    }

@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Redefine a senha do usuário a partir do token de recuperação.
    """
    try:
        payload = jwt.decode(request.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        token_type = payload.get("type")
        
        if not user_id or token_type != "reset_password":
            raise HTTPException(status_code=400, detail="Token inválido.")
            
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Token expirado.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=400, detail="Token inválido.")

    # Busca o usuário
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    # Atualiza a senha
    user.hashed_password = get_password_hash(request.new_password)
    db.add(user)
    await db.commit()

    return {"message": "Senha atualizada com sucesso."}
