"""Routes package - organized by function."""

from .auth_router import router as auth_router
from .analysis_router import router as analysis_router
from .health_router import router as health_router

__all__ = ["auth_router", "analysis_router", "health_router"]

