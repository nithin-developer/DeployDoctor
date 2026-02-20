"""
AI Repository Analyser - FastAPI Backend
Multi-agent system for code analysis and testing
"""
import sys
import asyncio

# Fix for Windows: asyncio.create_subprocess_exec requires ProactorEventLoop
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from routes.auth_router import router as auth_router
from routes.analysis_router import router as analysis_router
from routes.health_router import router as health_router
from config.settings import get_settings

settings = get_settings()

app = FastAPI(
    title="AI Repository Analyser",
    description="Multi-agent system for analyzing repositories, detecting bugs, and running tests",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(analysis_router)


if __name__ == "__main__":
    import uvicorn
    # Note: When running with --reload, use:
    # uvicorn main:app --reload --reload-exclude "temp_repos/*" --reload-exclude "results_cache/*"
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["temp_repos/*", "results_cache/*", "reports/*"]
    )
