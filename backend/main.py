from __future__ import annotations
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from api.routes import router
from api.schemas import ErrorResponse
from config.settings import settings
from db.neo4j_client import close_driver, get_driver, health_check
from utils.logger import get_logger
logger = get_logger(__name__)

# Application lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # STARTUP 
    logger.info("=" * 60)
    logger.info("Starting NL-Knowledge Graph Query System")
    logger.info("Environment: %s | Port: %d", settings.app_env, settings.backend_port)
    logger.info("=" * 60)

    # Warm up Neo4j connection
    try:
        driver = get_driver()
        neo4j_status = health_check()
        logger.info("Neo4j connected: %s", neo4j_status.get("status"))
        logger.info("  Node count: %s", neo4j_status.get("node_count", "unknown"))
    except Exception as e:
        logger.error("Neo4j connection failed at startup: %s", e)
        logger.warning("App will start but queries will fail until Neo4j is available")

    logger.info("API ready at http://localhost:%d", settings.backend_port)
    logger.info("Docs at http://localhost:%d/docs", settings.backend_port)

    yield 

    # SHUTDOWN
    logger.info("Shutting down application...")
    close_driver()
    logger.info("Neo4j driver closed. Goodbye.")

# App instantiation
app = FastAPI(
    title="NL-Academic Knowledge Graph",
    description=(
        "A production-grade system that converts natural language questions "
        "into Neo4j Cypher queries, executes them, and returns human-friendly answers. "
        "Domain: Academic Research Literature. "
        "Stack: Google Gemini · LangChain · Neo4j · FastAPI."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS — allow the React frontend to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{settings.frontend_port}",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request timing middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log method, path, status, and duration for every request."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s → %d (%.0fms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all exception handler that returns a structured JSON error
    instead of a raw 500 traceback. The full traceback is logged server-side.
    """
    logger.exception("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc) if settings.is_development else "An unexpected error occurred",
            status_code=500,
        ).model_dump(),
    )

# Routers
app.include_router(router, prefix="/api/v1", tags=["Knowledge Graph"])


# Root endpoint
@app.get("/", tags=["Root"])
async def root() -> dict:
    """API root — returns service info and link to docs."""
    return {
        "name": "NL-Academic Knowledge Graph API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
        "status": "running",
    }
