from datetime import datetime
from fastapi import APIRouter, Depends

from routes.auth_router import get_current_user
from models.users import User

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(current_user: User = Depends(get_current_user)):
    """Get dashboard stats for authenticated user."""
    return {
        "stats": {
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "pending_runs": 0
        },
        "recent_runs": [],
        "user": {
            "id": str(current_user.id),
            "full_name": current_user.full_name,
            "email": current_user.email
        }
    }
