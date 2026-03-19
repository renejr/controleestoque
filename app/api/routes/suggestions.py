from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.suggestion import Suggestion
from app.schemas.suggestion import SuggestionCreate, SuggestionResponse

router = APIRouter(prefix="/suggestions", tags=["Suggestions"])

@router.post("/", response_model=SuggestionResponse, status_code=201)
async def create_suggestion(
    suggestion_in: SuggestionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_suggestion = Suggestion(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        title=suggestion_in.title,
        description=suggestion_in.description,
        status="PENDING"
    )
    
    db.add(new_suggestion)
    await db.commit()
    await db.refresh(new_suggestion)
    return new_suggestion

@router.get("/", response_model=List[SuggestionResponse])
async def list_suggestions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(Suggestion).where(Suggestion.tenant_id == current_user.tenant_id)
    result = await db.execute(query)
    return result.scalars().all()
