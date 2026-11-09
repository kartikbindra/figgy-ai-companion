from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.database.connection import init_db
from app.api.chat import router as chat_router
from app.api.persona import router as persona_router
from app.api.memory import router as memory_router
from app.api.device import router as device_router
from app.api.health import router as health_router
from app.api.voice import router as voice_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}...")
    await init_db()
    logger.info("Database initialized successfully.")
    yield
    logger.info("Shutting down Figgy Backend...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    description="Backend intelligence server for Figgy — the unhinged handheld AI companion."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root health endpoints
app.include_router(health_router)

# Versioned API routes
app.include_router(chat_router, prefix=settings.API_V1_STR)
app.include_router(persona_router, prefix=settings.API_V1_STR)
app.include_router(memory_router, prefix=settings.API_V1_STR)
app.include_router(device_router, prefix=settings.API_V1_STR)
app.include_router(voice_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "message": "Figgy is awake, unhinged, and waiting in your palm.",
        "docs": "/docs"
    }
