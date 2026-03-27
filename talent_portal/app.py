# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Talent Portal Application
=============================================
Main FastAPI application for the Talent Portal.

Runs on port 9003 by default.

Start with:
    python start_talent.py

Or:
    python -m talent_portal.app
"""
import os
import sys
import logging
from datetime import datetime
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from talent_portal.config import config
from talent_portal.routes import router, templates, template_context

# Configure logging
os.makedirs(os.path.dirname(config.LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='[%(asctime)s] %(levelname)s %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.LOG_FILE) if config.LOG_FILE else logging.NullHandler()
    ]
)
logger = logging.getLogger('talent_portal')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("=" * 60)
    logger.info("ForgeForth Africa - Talent Portal Starting")
    logger.info("=" * 60)
    logger.info(f"Service: {config.SERVICE_NAME} v{config.SERVICE_VERSION}")
    logger.info(f"Environment: {'Development' if config.DEBUG else 'Production'}")
    logger.info(f"URL: http://{config.HOST}:{config.PORT}")
    logger.info(f"Auth Service: {config.AUTH_SERVICE_URL}")
    logger.info(f"API Service: {config.API_SERVICE_URL}")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("Talent Portal shutting down...")


# Create FastAPI app
app = FastAPI(
    title="ForgeForth Africa - Talent Portal",
    description="""
    The talent-facing web application for ForgeForth Africa.
    
    Features:
    - User registration and authentication
    - Profile management
    - Skills and experience tracking
    - Opportunity browsing and search
    - Application submission and tracking
    - AI-powered match recommendations
    - Notification center
    """,
    version=config.SERVICE_VERSION,
    docs_url="/api/docs" if config.DEBUG else None,
    redoc_url=None,
    lifespan=lifespan
)

# Session middleware (for login state)
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    max_age=config.SESSION_EXPIRE_MINUTES * 60
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
if config.STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")


# Exception handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 page."""
    if request.url.path.startswith('/api/'):
        return JSONResponse(
            content={'error': 'Not found'},
            status_code=404
        )
    return templates.TemplateResponse(
        "errors/404.html",
        template_context(request, page_title="Page Not Found"),
        status_code=404
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    """Custom 500 page."""
    logger.error(f"Server error: {exc}", exc_info=True)
    if request.url.path.startswith('/api/'):
        return JSONResponse(
            content={'error': 'Internal server error'},
            status_code=500
        )
    return templates.TemplateResponse(
        "errors/500.html",
        template_context(request, page_title="Server Error"),
        status_code=500
    )


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        'status': 'healthy',
        'service': config.SERVICE_NAME,
        'version': config.SERVICE_VERSION,
        'timestamp': datetime.utcnow().isoformat()
    }


# Include routes
app.include_router(router)


def main():
    """Run the talent portal."""
    import uvicorn

    uvicorn.run(
        "talent_portal.app:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level=config.LOG_LEVEL.lower()
    )


if __name__ == "__main__":
    main()

