from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    simple health check endpoint
    returns status and version info
    """
    return {
        "status": "healthy",
        "version": "1.0.0"
    }
