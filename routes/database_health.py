from fastapi import APIRouter, Depends
from database import get_pool_status, engine
from routes.auth import get_current_user
from models import User

router = APIRouter(prefix="/v1.0/database", tags=["Database Health"])

@router.get("/pool-status")
async def get_database_pool_status(current_user: User = Depends(get_current_user)):
    """Get current database connection pool status"""
    if current_user.user_status not in ["SUPER_USER", "ADMIN_USER"]:
        return {"error": "Insufficient permissions"}
    
    try:
        pool_status = get_pool_status()
        return {
            "status": "healthy" if pool_status["checked_out"] < 8 else "warning",
            "pool_metrics": pool_status,
            "recommendations": {
                "current_usage": f"{pool_status['checked_out']}/15 connections",
                "health_status": "good" if pool_status["checked_out"] < 8 else "needs_attention"
            }
        }
    except Exception as e:
        return {"error": f"Failed to get pool status: {str(e)}"}

@router.post("/pool-reset")
async def reset_database_pool(current_user: User = Depends(get_current_user)):
    """Reset database connection pool (emergency use only)"""
    if current_user.user_status != "SUPER_USER":
        return {"error": "Only SUPER_USER can reset connection pool"}
    
    try:
        engine.dispose()
        return {"message": "Database connection pool has been reset"}
    except Exception as e:
        return {"error": f"Failed to reset pool: {str(e)}"}