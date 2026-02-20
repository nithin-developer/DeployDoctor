"""Analysis routes for repository analysis operations."""

import os
import json
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import Response
from pydantic import BaseModel
import uuid

import analysis_schemas
from services.analysis_service import analysis_service
from services.github_service import github_service
from utils.report_generator import ReportGenerator

router = APIRouter(prefix="/api/analyze", tags=["analysis"])

# Results persistence directory
RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results_cache")
os.makedirs(RESULTS_DIR, exist_ok=True)

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


@router.post("", response_model=AnalyzeResponse)
async def start_analysis(request: analysis_schemas.AnalysisRequest, background_tasks: BackgroundTasks):
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


@router.get("/{analysis_id}/status", response_model=analysis_schemas.AnalysisStatus)
async def get_analysis_status(analysis_id: str):
    """Get the current status of an analysis"""
    status_data = analysis_service.get_analysis_status(analysis_id)
    
    # If status is not_found, check if there's a completed result on disk
    # (this handles the case where server restarted after analysis completed)
    if status_data.get("status") == "not_found":
        result = _load_result_from_disk(analysis_id)
        if result:
            return analysis_schemas.AnalysisStatus(
                status="completed",
                progress=100,
                current_step="completed",
                message="Analysis completed"
            )
    
    return analysis_schemas.AnalysisStatus(
        status=status_data.get("status", "unknown"),
        progress=status_data.get("progress", 0),
        current_step=status_data.get("status", "unknown"),
        message=status_data.get("message", "")
    )


@router.get("/{analysis_id}/result")
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


@router.delete("/{analysis_id}")
async def cancel_analysis(analysis_id: str):
    """Cancel an ongoing analysis"""
    analysis_service.cleanup_analysis(analysis_id)
    
    if analysis_id in analysis_results:
        del analysis_results[analysis_id]
    
    return {"message": "Analysis cancelled"}


class CIStatusResponse(BaseModel):
    status: str  # pending, running, success, failure, unknown
    conclusion: Optional[str] = None
    workflow_url: Optional[str] = None
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    merged: bool = False
    message: str = ""


@router.get("/{analysis_id}/ci-status", response_model=CIStatusResponse)
async def get_ci_status(analysis_id: str, github_token: Optional[str] = None):
    """
    Get CI/CD status for an analysis.
    
    Checks GitHub Actions workflow status for the PR branch.
    Pass github_token as query param if not stored in result.
    """
    # Get result from memory or disk
    result = analysis_results.get(analysis_id)
    if not result:
        result = _load_result_from_disk(analysis_id)
        if result:
            analysis_results[analysis_id] = result
    
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Extract PR info from result
    result_dict = result if isinstance(result, dict) else (
        result.model_dump() if hasattr(result, 'model_dump') else result.dict()
    )
    
    pr_url = result_dict.get("pr_url")
    pr_number = result_dict.get("pr_number")
    repo_url = result_dict.get("repo_url")
    branch_name = result_dict.get("branch_name")
    
    if not pr_url or not pr_number:
        return CIStatusResponse(
            status="unknown",
            message="No PR was created for this analysis",
            pr_url=None,
            pr_number=None,
            merged=False
        )
    
    # Get token from request or result metadata
    token = github_token
    if not token:
        # Try to get from result summary if stored
        summary = result_dict.get("summary", {})
        token = summary.get("github_token")
    
    if not token:
        return CIStatusResponse(
            status="unknown",
            pr_url=pr_url,
            pr_number=pr_number,
            merged=result_dict.get("merged", False),
            message="GitHub token required to check CI status"
        )
    
    try:
        # Get CI status from GitHub
        ci_result = await github_service.get_latest_workflow_run(
            repo_url=repo_url,
            branch=branch_name,
            github_token=token
        )
        
        status_map = {
            "queued": "pending",
            "in_progress": "running",
            "completed": ci_result.conclusion or "unknown"
        }
        
        return CIStatusResponse(
            status=status_map.get(ci_result.status, ci_result.status),
            conclusion=ci_result.conclusion,
            workflow_url=ci_result.workflow_url,
            pr_url=pr_url,
            pr_number=pr_number,
            merged=result_dict.get("merged", False),
            message=ci_result.message
        )
    except Exception as e:
        return CIStatusResponse(
            status="unknown",
            pr_url=pr_url,
            pr_number=pr_number,
            merged=result_dict.get("merged", False),
            message=f"Error checking CI status: {str(e)}"
        )


@router.post("/{analysis_id}/merge")
async def merge_pr(analysis_id: str, github_token: str):
    """
    Manually trigger PR merge for an analysis.
    
    Use this if auto-merge is disabled or CI monitoring stopped.
    """
    # Get result from memory or disk
    result = analysis_results.get(analysis_id)
    if not result:
        result = _load_result_from_disk(analysis_id)
        if result:
            analysis_results[analysis_id] = result
    
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    result_dict = result if isinstance(result, dict) else (
        result.model_dump() if hasattr(result, 'model_dump') else result.dict()
    )
    
    pr_number = result_dict.get("pr_number")
    repo_url = result_dict.get("repo_url")
    
    if not pr_number:
        raise HTTPException(status_code=400, detail="No PR was created for this analysis")
    
    if result_dict.get("merged"):
        return {"status": "already_merged", "message": "PR was already merged"}
    
    try:
        merge_result = await github_service.merge_pull_request(
            repo_url=repo_url,
            pr_number=pr_number,
            github_token=github_token
        )
        
        if merge_result.success:
            # Update result to mark as merged
            if isinstance(result, dict):
                result["merged"] = True
            elif hasattr(result, "merged"):
                result.merged = True
            _save_result_to_disk(analysis_id, result)
            
            return {
                "status": "merged",
                "message": merge_result.message,
                "merge_sha": merge_result.merge_sha
            }
        else:
            raise HTTPException(status_code=400, detail=merge_result.message)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Merge failed: {str(e)}")


@router.get("/{analysis_id}/report/json")
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


@router.get("/{analysis_id}/report/pdf")
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
