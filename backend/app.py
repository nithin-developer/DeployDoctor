import os
import sys
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

# Fix for Windows: asyncio.create_subprocess_exec requires ProactorEventLoop
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import routers
from routes.auth_router import router as auth_router
from routes.agent_router import router as agent_router
from routes.dashboard_router import router as dashboard_router
from routes.analysis_router import router as analysis_router

# Import database
from config.database import init_db
from config.settings import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup
    print(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Initialize database (create tables if they don't exist)
    # In production, use Alembic migrations instead
    if settings.DEBUG:
        await init_db()
        print("📦 Database initialized")
    
    yield
    
    # Shutdown
    print("👋 Shutting down...")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered CI/CD pipeline agent for automated code fixes",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS configuration
allowed_origins = [
    origin.strip()
    for origin in settings.FRONTEND_ORIGINS.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ HEALTH CHECK ============

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    from services.analysis_service import analysis_service
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": settings.APP_VERSION,
        "app": settings.APP_NAME,
        "agents": {
            "code_review": "active",
            "test_runner": "active",
            "orchestrator": "active",
            "code_fixer": "active",
            "test_generator": "active"
        },
        "active_analyses": len(analysis_service.active_analyses)
    }


# ============ INCLUDE ROUTERS ============

# Auth routes: /api/auth/*
app.include_router(auth_router)

# Agent routes: /run-agent, /api/generate-branch, /api/validate-repo
app.include_router(agent_router)

# Dashboard routes: /api/dashboard/*
app.include_router(dashboard_router)

# Analysis routes: /api/analyze/*
app.include_router(analysis_router)


# ============ ROOT ============

@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        reload_excludes=["temp_repos/*", "results_cache/*", "reports/*"]
    )
