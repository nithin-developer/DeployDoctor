"""
Agent Service - Delegates to Multi-Agent Orchestrator

This service wraps the multi-agent orchestrator system.
All the actual work is done by specialized agents:

- OrchestratorAgent: Main coordinator
- SandboxExecutorAgent: Runs tests in Docker
- ErrorParserAgent: Parses errors
- CodeFixerAgent: Generates fixes via LLM
- TestRunnerAgent: Discovers and runs tests
- CIMonitorAgent: Monitors GitHub Actions
"""

import uuid
import time
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from config.settings import get_settings
from schemas.agent import (
    AgentRequest,
    AgentResponse,
    AgentStatus,
    AgentRunLog,
    ProjectType
)
from schemas.results import (
    AgentResults,
    IterationResult,
    FixEntry,
    FixStatus,
    CIStatusResult
)
from agents import OrchestratorAgent
from agents.base_agent import AgentStatus as OrchestratorStatus
from utils.branch import generate_branch_name

settings = get_settings()


class AgentService:
    """
    Service for orchestrating CI/CD agent operations.
    
    Delegates to the multi-agent orchestrator system.
    """
    
    def __init__(self):
        self.max_retries = settings.MAX_RETRIES
        self.orchestrator = OrchestratorAgent(
            github_token=settings.GITHUB_TOKEN
        )
    
    def _add_log(
        self,
        logs: list,
        status: AgentStatus,
        message: str
    ) -> None:
        """Add a log entry."""
        logs.append(AgentRunLog(
            timestamp=datetime.utcnow(),
            status=status,
            message=message
        ))
    
    def _convert_orchestrator_result(
        self,
        orch_data: dict,
        request: AgentRequest,
        run_id: str,
        logs: list,
        start_time: float
    ) -> AgentResponse:
        """Convert orchestrator result to AgentResponse format."""
        # Build AgentResults from orchestrator data
        results = AgentResults(
            repo_url=request.repo_url,
            branch_name=orch_data.get("branch_name", ""),
            team_name=request.team_name,
            leader_name=request.leader_name,
            run_id=run_id,
            start_time=datetime.utcnow()
        )
        
        results.total_iterations = orch_data.get("total_iterations", 0)
        results.total_commits = orch_data.get("total_commits", 0)
        results.total_fixes_applied = orch_data.get("total_fixes", 0)
        results.tests_passing = orch_data.get("success", False)
        results.time_taken_seconds = orch_data.get("total_duration_seconds", time.time() - start_time)
        results.end_time = datetime.utcnow()
        
        # Convert iterations
        for iter_data in orch_data.get("iterations", []):
            iter_result = IterationResult(
                iteration_number=iter_data.get("iteration", 0),
                tests_passed=iter_data.get("success", False),
                tests_failed_count=iter_data.get("errors_found", 0),
                tests_passed_count=0,
                errors_found=iter_data.get("errors_found", 0),
                fixes_applied=iter_data.get("fixes_applied", 0),
                duration_seconds=iter_data.get("duration_seconds", 0.0)
            )
            results.iterations.append(iter_result)
            
            # Add fix entry if commit was made
            if iter_data.get("commit_sha"):
                fix_entry = FixEntry(
                    iteration=iter_data.get("iteration", 0),
                    file_path="(multiple files)",
                    line_number=0,
                    bug_type="AUTO_FIX",
                    fix_description=iter_data.get("message", "Auto-fix applied"),
                    status=FixStatus.SUCCESS if iter_data.get("success") else FixStatus.PARTIAL,
                    commit_sha=iter_data.get("commit_sha")
                )
                results.fix_table.append(fix_entry)
        
        # Set CI status based on final result
        if orch_data.get("success"):
            results.ci_status = CIStatusResult.PASSING
        elif orch_data.get("final_status") == "PARTIAL":
            results.ci_status = CIStatusResult.FAILING
        else:
            results.ci_status = CIStatusResult.UNKNOWN
        
        # Determine final status
        success = orch_data.get("success", False)
        final_status = AgentStatus.COMPLETED if success else AgentStatus.FAILED
        score = orch_data.get("score", 0)
        
        if success:
            final_message = f"All tests passing! Score: {score}"
        else:
            final_message = f"Fix attempt completed. Applied {results.total_fixes_applied} fixes."
        
        self._add_log(logs, final_status, final_message)
        
        return AgentResponse(
            success=success,
            message=final_message,
            run_id=run_id,
            branch_name=orch_data.get("branch_name", ""),
            repo_url=request.repo_url,
            team_name=request.team_name,
            leader_name=request.leader_name,
            project_type=None,
            temp_dir=None,
            status=final_status,
            logs=logs,
            error=None if success else orch_data.get("final_status"),
            results_json=results.to_results_json()
        )
    
    async def run_agent(self, request: AgentRequest) -> AgentResponse:
        """
        Execute the full CI/CD agent workflow using the orchestrator.
        
        Delegates to the OrchestratorAgent which coordinates all agents.
        
        Args:
            request: AgentRequest with repo_url, team_name, leader_name
            
        Returns:
            AgentResponse with status, logs, and results
        """
        run_id = str(uuid.uuid4())[:8]
        logs = []
        start_time = time.time()
        
        # Generate branch name for logging
        branch_name = generate_branch_name(request.team_name, request.leader_name)
        
        self._add_log(logs, AgentStatus.PENDING, f"Starting agent run: {run_id}")
        self._add_log(logs, AgentStatus.PENDING, f"Target branch: {branch_name}")
        
        # Progress callback for logs
        def on_progress(stage: str, percent: int, message: str):
            status_map = {
                "cloning": AgentStatus.CLONING,
                "iteration": AgentStatus.TESTING,
                "testing": AgentStatus.TESTING,
                "parsing": AgentStatus.ANALYZING,
                "fixing": AgentStatus.FIXING,
                "committing": AgentStatus.FIXING,
                "monitoring": AgentStatus.ANALYZING,
                "complete": AgentStatus.COMPLETED
            }
            status = status_map.get(stage, AgentStatus.PENDING)
            self._add_log(logs, status, f"[{percent}%] {message}")
        
        # Set up orchestrator with progress callback
        self.orchestrator.set_progress_callback(on_progress)
        
        try:
            self._add_log(logs, AgentStatus.CLONING, f"Analyzing repository: {request.repo_url}")
            
            # Execute the orchestrator
            result = await self.orchestrator.execute({
                "repo_url": request.repo_url,
                "team_name": request.team_name,
                "leader_name": request.leader_name,
                "max_iterations": self.max_retries
            })
            
            # Convert orchestrator result to response format
            if result.status == OrchestratorStatus.SUCCESS:
                return self._convert_orchestrator_result(
                    result.data,
                    request,
                    run_id,
                    logs,
                    start_time
                )
            else:
                # Handle orchestrator failure
                self._add_log(logs, AgentStatus.FAILED, f"Orchestrator failed: {result.error}")
                
                results = AgentResults(
                    repo_url=request.repo_url,
                    branch_name=branch_name,
                    team_name=request.team_name,
                    leader_name=request.leader_name,
                    run_id=run_id,
                    start_time=datetime.utcnow()
                )
                results.error_message = result.error
                results.end_time = datetime.utcnow()
                results.time_taken_seconds = time.time() - start_time
                
                # If there's partial data, use it
                if result.data:
                    return self._convert_orchestrator_result(
                        result.data,
                        request,
                        run_id,
                        logs,
                        start_time
                    )
                
                return AgentResponse(
                    success=False,
                    message=result.error or "Orchestrator failed",
                    run_id=run_id,
                    branch_name=branch_name,
                    repo_url=request.repo_url,
                    team_name=request.team_name,
                    leader_name=request.leader_name,
                    project_type=None,
                    temp_dir=None,
                    status=AgentStatus.FAILED,
                    logs=logs,
                    error=result.error,
                    results_json=results.to_results_json()
                )
                
        except Exception as e:
            self._add_log(logs, AgentStatus.FAILED, f"Unexpected error: {str(e)}")
            
            results = AgentResults(
                repo_url=request.repo_url,
                branch_name=branch_name,
                team_name=request.team_name,
                leader_name=request.leader_name,
                run_id=run_id,
                start_time=datetime.utcnow()
            )
            results.error_message = str(e)
            results.end_time = datetime.utcnow()
            results.time_taken_seconds = time.time() - start_time
            
            return AgentResponse(
                success=False,
                message="Agent execution failed",
                run_id=run_id,
                branch_name=branch_name,
                repo_url=request.repo_url,
                team_name=request.team_name,
                leader_name=request.leader_name,
                project_type=None,
                temp_dir=None,
                status=AgentStatus.FAILED,
                logs=logs,
                error=str(e),
                results_json=results.to_results_json()
            )
    
    def cleanup_run(self, temp_dir: str) -> None:
        """Clean up after a run - no longer needed with orchestrator."""
        pass
    
    def get_results_json(self, results: AgentResults) -> dict:
        """Get results in JSON format for frontend/export."""
        return results.to_results_json()


# Singleton instance
agent_service = AgentService()
