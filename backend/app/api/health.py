from fastapi import APIRouter
from app.llm.orchestrator import orchestrator
from app.core.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """System health check endpoint."""
    llm_health = await orchestrator.provider.health_check()
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_status": llm_health
    }


@router.get("/health/model")
async def model_health():
    """Detailed model status."""
    return await orchestrator.provider.health_check()
