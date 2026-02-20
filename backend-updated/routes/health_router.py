"""Health check routes."""

from fastapi import APIRouter
from services.analysis_service import analysis_service

router = APIRouter(tags=["health"])


@router.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "AI Repository Analyser",
        "version": "1.0.0"
    }


@router.get("/api/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "agents": {
            "code_review": "active",
            "test_runner": "active",
            "orchestrator": "active",
            "code_fixer": "active",
            "test_generator": "active"
        },
        "active_analyses": len(analysis_service.active_analyses)
    }
