from fastapi import APIRouter, HTTPException, Query

from schemas.agent import (
    AgentRequest,
    AgentResponse,
    BranchNameResponse,
    RepoValidationResponse,
    ProjectDetectionResponse,
    ProjectType
)
from services.agent_service import agent_service
from services.git_service import git_service
from utils.branch import generate_branch_name, validate_github_url

router = APIRouter(tags=["agent"])


@router.post("/run-agent", response_model=AgentResponse)
async def run_agent(request: AgentRequest):
    """
    Main endpoint for running the CI/CD agent.
    
    This endpoint:
    1. Validates the input (repo URL, team name, leader name)
    2. Clones the repository to a unique temp directory
    3. Creates a branch with the generated name (TEAM_NAME_LEADER_NAME_AI_Fix)
    4. Detects project type (Python/Node)
    5. Returns status and logs
    
    ⚠️ CRITICAL: Never pushes to main branch
    """
    return await agent_service.run_agent(request)


@router.post("/api/generate-branch", response_model=BranchNameResponse)
async def generate_branch(
    team_name: str = Query(..., min_length=2, max_length=50),
    leader_name: str = Query(..., min_length=2, max_length=50)
):
    """
    Utility endpoint to preview the generated branch name.
    Useful for validation before running the full agent.
    """
    branch_name = generate_branch_name(team_name.strip(), leader_name.strip())
    
    return BranchNameResponse(
        branch_name=branch_name,
        team_name=team_name.strip(),
        leader_name=leader_name.strip()
    )


@router.get("/api/validate-repo", response_model=RepoValidationResponse)
async def validate_repo(url: str = Query(..., min_length=1)):
    """
    Validate if a GitHub repository URL is valid.
    """
    url = url.strip()
    
    if not validate_github_url(url):
        return RepoValidationResponse(
            valid=False,
            url=url,
            error="Invalid GitHub repository URL format. Must be: https://github.com/owner/repo"
        )
    
    return RepoValidationResponse(
        valid=True,
        url=url,
        message="Repository URL format is valid"
    )


@router.post("/api/cleanup")
async def cleanup_run(temp_dir: str):
    """
    Clean up a temporary directory from a previous run.
    """
    if not temp_dir:
        raise HTTPException(status_code=400, detail="temp_dir is required")
    
    try:
        agent_service.cleanup_run(temp_dir)
        return {"success": True, "message": f"Cleaned up: {temp_dir}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
