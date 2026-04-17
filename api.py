# API Server for LegalDebateAI
# Quick HTTP API for running debate analysis

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any
import json
from datetime import datetime
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import debate engine
from debate_engine import run_debate

# Initialize FastAPI app
app = FastAPI(
    title="LegalDebateAI API",
    description="Analyze Government Orders with AI-powered legal debate",
    version="1.0.0"
)

# Models
class DebateRequest(BaseModel):
    """Debate analysis request"""
    go_text: str
    use_cache: bool = True
    verbose: bool = False

class DebateResponse(BaseModel):
    """Debate analysis response"""
    status: str
    message: str
    timestamp: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    version: str

# Routes
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "service": "LegalDebateAI",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "analyze": "/analyze",
            "docs": "/docs"
        }
    }

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="1.0.0"
    )

@app.post("/analyze", response_model=DebateResponse, tags=["Analysis"])
async def analyze_go(request: DebateRequest):
    """
    Analyze a Government Order
    
    - **go_text**: The Government Order text to analyze
    - **use_cache**: Enable caching for faster results (default: true)
    - **verbose**: Print detailed analysis steps (default: false)
    
    Returns: Complete debate analysis with verdict and recommendations
    """
    try:
        if not request.go_text or len(request.go_text.strip()) < 50:
            raise ValueError("GO text must be at least 50 characters")
        
        logger.info("Starting debate analysis")
        
        # Run debate analysis
        result = run_debate(
            request.go_text,
            verbose=request.verbose,
            use_cache=request.use_cache
        )
        
        logger.info("Debate analysis completed successfully")
        
        return DebateResponse(
            status="success",
            message="Analysis completed successfully",
            timestamp=datetime.now().isoformat(),
            result=result,
            error=None
        )
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/status", tags=["Status"])
async def system_status():
    """Get system status"""
    try:
        import chromadb
        from config import ANTHROPIC_API_KEY
        
        chroma_path = Path("db/chromadb")
        client = chromadb.PersistentClient(path=str(chroma_path))
        collections = client.list_collections()
        
        return {
            "status": "operational",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "api": "running",
                "database": "connected",
                "cache": "enabled",
                "collections": len(collections),
                "api_key": "configured" if ANTHROPIC_API_KEY else "missing"
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

@app.get("/stats", tags=["Statistics"])
async def statistics():
    """Get system statistics"""
    try:
        import os
        from pathlib import Path
        
        cache_dir = Path("db/cache")
        chroma_dir = Path("db/chromadb")
        
        cache_size = sum(f.stat().st_size for f in cache_dir.glob('**/*') if f.is_file()) if cache_dir.exists() else 0
        
        return {
            "timestamp": datetime.now().isoformat(),
            "cache": {
                "size_bytes": cache_size,
                "size_mb": round(cache_size / (1024*1024), 2)
            },
            "database": {
                "path": str(chroma_dir),
                "exists": chroma_dir.exists()
            }
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/batch", tags=["Batch"])
async def batch_analyze(requests: list[DebateRequest], background_tasks: BackgroundTasks):
    """
    Analyze multiple Government Orders (batch mode)
    
    - **requests**: List of GO text analysis requests
    
    Note: Large batches are processed in background
    """
    if len(requests) > 100:
        raise HTTPException(status_code=400, detail="Max 100 items per batch")
    
    results = []
    for idx, req in enumerate(requests):
        try:
            result = run_debate(req.go_text, use_cache=req.use_cache, verbose=False)
            results.append({
                "index": idx,
                "status": "success",
                "result": result
            })
        except Exception as e:
            results.append({
                "index": idx,
                "status": "error",
                "error": str(e)
            })
    
    return {
        "timestamp": datetime.now().isoformat(),
        "total": len(requests),
        "succeeded": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "error"),
        "results": results
    }

# Error handlers
@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    """Generic exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return {
        "error": "Internal server error",
        "timestamp": datetime.now().isoformat()
    }

# Events
@app.on_event("startup")
async def startup_event():
    """On startup"""
    logger.info("LegalDebateAI API starting up")
    
    # Verify configuration
    try:
        from config import ANTHROPIC_API_KEY
        if not ANTHROPIC_API_KEY:
            logger.warning("ANTHROPIC_API_KEY not configured")
    except Exception as e:
        logger.warning(f"Configuration check failed: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """On shutdown"""
    logger.info("LegalDebateAI API shutting down")

if __name__ == "__main__":
    import uvicorn
    
    # Run server
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
