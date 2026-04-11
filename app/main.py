"""
URL Shortener API - A simple in-memory URL shortening service
Built for learning Kubernetes deployment on GKE
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl
from datetime import datetime
import hashlib
import os

app = FastAPI(
    title="URL Shortener API",
    description="A simple URL shortening service for K8s learning",
    version="1.0.0"
)

# In-memory storage (in production, use Redis or a database)
url_database: dict[str, dict] = {}

# Get environment variables (will come from ConfigMap)
APP_NAME = os.getenv("APP_NAME", "url-shortener")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")


class URLRequest(BaseModel):
    """Request model for URL shortening"""
    url: HttpUrl


class URLResponse(BaseModel):
    """Response model for shortened URL"""
    original_url: str
    short_code: str
    short_url: str
    created_at: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    app_name: str
    environment: str
    timestamp: str
    total_urls: int


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information"""
    return {
        "app": APP_NAME,
        "environment": ENVIRONMENT,
        "message": "Welcome to the URL Shortener API!",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint for Kubernetes liveness/readiness probes.
    Returns the current status of the application.
    """
    return HealthResponse(
        status="healthy",
        app_name=APP_NAME,
        environment=ENVIRONMENT,
        timestamp=datetime.utcnow().isoformat(),
        total_urls=len(url_database)
    )


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """
    Readiness probe endpoint.
    Checks if the application is ready to receive traffic.
    """
    return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}


@app.post("/shorten", response_model=URLResponse, status_code=status.HTTP_201_CREATED, tags=["URLs"])
async def shorten_url(request: URLRequest):
    """
    Create a shortened URL.
    Takes a long URL and returns a short code that can be used to redirect.
    """
    url_str = str(request.url)
    
    # Generate short code using hash
    hash_object = hashlib.md5(url_str.encode())
    short_code = hash_object.hexdigest()[:8]
    
    # Store in database
    url_database[short_code] = {
        "original_url": url_str,
        "created_at": datetime.utcnow().isoformat(),
        "visits": 0
    }
    
    return URLResponse(
        original_url=url_str,
        short_code=short_code,
        short_url=f"{BASE_URL}/r/{short_code}",
        created_at=url_database[short_code]["created_at"]
    )


@app.get("/r/{short_code}", tags=["URLs"])
async def redirect_to_url(short_code: str):
    """
    Redirect to the original URL using the short code.
    """
    if short_code not in url_database:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Short URL not found"
        )
    
    url_database[short_code]["visits"] += 1
    return RedirectResponse(url=url_database[short_code]["original_url"])


@app.get("/stats/{short_code}", tags=["URLs"])
async def get_url_stats(short_code: str):
    """
    Get statistics for a shortened URL.
    """
    if short_code not in url_database:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Short URL not found"
        )
    
    data = url_database[short_code]
    return {
        "short_code": short_code,
        "original_url": data["original_url"],
        "created_at": data["created_at"],
        "visits": data["visits"]
    }


@app.get("/urls", tags=["URLs"])
async def list_all_urls():
    """
    List all shortened URLs (for debugging/demo purposes).
    """
    return {
        "total": len(url_database),
        "urls": [
            {
                "short_code": code,
                "original_url": data["original_url"],
                "visits": data["visits"]
            }
            for code, data in url_database.items()
        ]
    }
