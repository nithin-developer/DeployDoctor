"""
AI Repository Analyser - FastAPI Backend
Multi-agent system for code analysis and testing
"""
import os
import sys
import json
import uuid
import asyncio

# Fix for Windows: asyncio.create_subprocess_exec requires ProactorEventLoop
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from models import AnalysisRequest, AnalysisResult, AnalysisStatus
from services.analysis_service import analysis_service
from utils.report_generator import ReportGenerator

# Results persistence directory
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results_cache")
os.makedirs(RESULTS_DIR, exist_ok=True)

app = FastAPI(
    title="AI Repository Analyser",
    description="Multi-agent system for analyzing repositories, detecting bugs, and running tests",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store for analysis results (with disk persistence)
analysis_results: Dict[str, Any] = {}


def _save_result_to_disk(analysis_id: str, result: Any):
    """Persist analysis result to disk"""
    try:
        filepath = os.path.join(RESULTS_DIR, f"{analysis_id}.json")
        result_dict = result.model_dump() if hasattr(result, 'model_dump') else (
            result.dict() if hasattr(result, 'dict') else result
        )
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, default=str)
    except Exception as e:
        print(f"Warning: Could not persist result to disk: {e}")


def _load_result_from_disk(analysis_id: str) -> Optional[Dict]:
    """Load analysis result from disk"""
    try:
        filepath = os.path.join(RESULTS_DIR, f"{analysis_id}.json")
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load result from disk: {e}")
    return None


class AnalyzeResponse(BaseModel):
    analysis_id: str
    message: str


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "AI Repository Analyser",
        "version": "1.0.0"
    }


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def start_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks):
    """
    Start repository analysis
    
    This endpoint initiates the multi-agent analysis process:
    1. Code Review Agent analyzes code line by line
    2. Test Runner Agent discovers and runs tests
    3. Orchestrator Agent coordinates and applies fixes
    """
    analysis_id = str(uuid.uuid4())
    
    async def run_analysis():
        try:
            result = await analysis_service.analyze_repository(request, analysis_id)
            analysis_results[analysis_id] = result
            # Persist to disk for crash/reload recovery
            _save_result_to_disk(analysis_id, result)
        except Exception as e:
            analysis_service.active_analyses[analysis_id] = {
                "status": "error",
                "progress": 0,
                "message": str(e)
            }
    
    background_tasks.add_task(run_analysis)
    
    return AnalyzeResponse(
        analysis_id=analysis_id,
        message="Analysis started successfully"
    )


@app.get("/api/analyze/{analysis_id}/status", response_model=AnalysisStatus)
async def get_analysis_status(analysis_id: str):
    """Get the current status of an analysis"""
    status_data = analysis_service.get_analysis_status(analysis_id)
    
    # If status is not_found, check if there's a completed result on disk
    # (this handles the case where server restarted after analysis completed)
    if status_data.get("status") == "not_found":
        result = _load_result_from_disk(analysis_id)
        if result:
            return AnalysisStatus(
                status="completed",
                progress=100,
                current_step="completed",
                message="Analysis completed"
            )
    
    return AnalysisStatus(
        status=status_data.get("status", "unknown"),
        progress=status_data.get("progress", 0),
        current_step=status_data.get("status", "unknown"),
        message=status_data.get("message", "")
    )


@app.get("/api/analyze/{analysis_id}/result")
async def get_analysis_result(analysis_id: str):
    """Get the result of a completed analysis"""
    
    # First try to get from memory
    result = analysis_results.get(analysis_id)
    
    # If not in memory, try to load from disk (e.g., after server restart)
    if not result:
        result = _load_result_from_disk(analysis_id)
        if result:
            analysis_results[analysis_id] = result  # Cache in memory
    
    # If we found a result, return it
    if result:
        return {
            "status": "completed",
            "result": result
        }
    
    # Check if analysis is still running
    status = analysis_service.get_analysis_status(analysis_id)
    
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    if status.get("status") not in ["completed", "error"]:
        return {
            "status": "pending",
            "progress": status.get("progress", 0),
            "message": status.get("message", "Analysis in progress...")
        }
    
    return {
        "status": "error",
        "message": status.get("message", "Analysis failed")
    }


@app.delete("/api/analyze/{analysis_id}")
async def cancel_analysis(analysis_id: str):
    """Cancel an ongoing analysis"""
    analysis_service.cleanup_analysis(analysis_id)
    
    if analysis_id in analysis_results:
        del analysis_results[analysis_id]
    
    return {"message": "Analysis cancelled"}


@app.get("/api/health")
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


@app.get("/api/analyze/{analysis_id}/report/json")
async def get_json_report(analysis_id: str):
    """Download analysis result as JSON report"""
    result = analysis_results.get(analysis_id)
    
    # Try to load from disk if not in memory
    if not result:
        result = _load_result_from_disk(analysis_id)
        if result:
            analysis_results[analysis_id] = result
    
    if not result:
        raise HTTPException(status_code=404, detail="Analysis result not found")
    
    # Convert result to dict if needed
    result_dict = result.model_dump() if hasattr(result, 'model_dump') else (
        result.dict() if hasattr(result, 'dict') else result
    )
    
    report_gen = ReportGenerator()
    json_content = report_gen.generate_json_report(result_dict)
    
    return Response(
        content=json_content,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="analysis_report_{analysis_id[:8]}.json"'
        }
    )


@app.get("/api/analyze/{analysis_id}/report/pdf")
async def get_pdf_report(analysis_id: str):
    """Download analysis result as PDF report"""
    result = analysis_results.get(analysis_id)
    
    # Try to load from disk if not in memory
    if not result:
        result = _load_result_from_disk(analysis_id)
        if result:
            analysis_results[analysis_id] = result
    
    if not result:
        raise HTTPException(status_code=404, detail="Analysis result not found")
    
    # Convert result to dict if needed
    result_dict = result.model_dump() if hasattr(result, 'model_dump') else (
        result.dict() if hasattr(result, 'dict') else result
    )
    
    report_gen = ReportGenerator()
    pdf_bytes = report_gen.generate_pdf_report(result_dict)
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="analysis_report_{analysis_id[:8]}.pdf"'
        }
    )


if __name__ == "__main__":
    import uvicorn
    # Note: When running with --reload, use:
    # uvicorn main:app --reload --reload-exclude "temp_repos/*" --reload-exclude "results_cache/*"
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["temp_repos/*", "results_cache/*", "reports/*"]
    )
