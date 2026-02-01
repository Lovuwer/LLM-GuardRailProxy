import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.routers import health, prompt


# setup structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    startup and shutdown events
    """
    # startup
    logger.info("starting llm guardrail proxy")
    logger.info("llm guardrail proxy started", environment=settings.ENVIRONMENT)
    
    yield
    
    # shutdown
    logger.info("shutting down llm guardrail proxy")


# create fastapi app
app = FastAPI(
    title="LLM Guardrail Proxy",
    lifespan=lifespan
)

# add rate limiter state
app.state.limiter = prompt.limiter

# cors middleware - allow all origins for dev
# note: in production, restrict origins and disable credentials with wildcard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# root route serving the dashboard
@app.get("/")
async def read_root():
    """
    serve the main dashboard html
    """
    return FileResponse("app/static/index.html")

# exception handlers
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """
    handle rate limit exceeded errors
    """
    logger.warning("rate limit exceeded", path=request.url.path)
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "error": "rate limit exceeded",
            "detail": str(exc.detail)
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    global exception handler - fail closed on unexpected errors
    """
    logger.error("unhandled exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "internal server error",
            "detail": "an unexpected error occurred"
        }
    )


# include routers
app.include_router(health.router)
app.include_router(prompt.router)
