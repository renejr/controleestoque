from fastapi import APIRouter

router = APIRouter()

@router.get("/health", status_code=200)
async def health_check():
    """
    Endpoint de verificação de integridade da API.
    """
    return {"status": "ok", "message": "Inventory SaaS API is running."}
