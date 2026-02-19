"""
CI Monitor Service for GitHub Actions

Phase 8: Monitor CI/CD pipeline status.

Monitors:
- GitHub Actions workflow runs
- Build status
- Test results
"""

import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import httpx

from config.settings import get_settings
from utils.branch import extract_repo_info

settings = get_settings()


class CIStatus(str, Enum):
    """CI pipeline status."""
    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass
class WorkflowRun:
    """GitHub Actions workflow run information."""
    id: int
    name: str
    status: CIStatus
    conclusion: Optional[CIStatus]
    branch: str
    commit_sha: str
    created_at: str
    updated_at: str
    url: str
    
    @property
    def is_complete(self) -> bool:
        return self.status == CIStatus.COMPLETED
    
    @property
    def is_success(self) -> bool:
        return self.conclusion == CIStatus.SUCCESS
    
    @property
    def is_failure(self) -> bool:
        return self.conclusion == CIStatus.FAILURE


class CIMonitor:
    """
    Service for monitoring GitHub Actions CI/CD pipeline.
    
    Capabilities:
    - Check latest workflow run status
    - Wait for workflow completion
    - Get workflow run details
    """
    
    GITHUB_API_BASE = "https://api.github.com"
    
    def __init__(self):
        self.token = settings.GITHUB_TOKEN
        self._client: Optional[httpx.Client] = None
    
    @property
    def client(self) -> httpx.Client:
        """Get HTTP client with GitHub auth headers."""
        if self._client is None:
            headers = {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            
            self._client = httpx.Client(
                base_url=self.GITHUB_API_BASE,
                headers=headers,
                timeout=30.0
            )
        return self._client
    
    def _parse_status(self, status: str) -> CIStatus:
        """Parse GitHub status string to CIStatus enum."""
        mapping = {
            "queued": CIStatus.QUEUED,
            "in_progress": CIStatus.IN_PROGRESS,
            "completed": CIStatus.COMPLETED,
            "waiting": CIStatus.PENDING,
            "pending": CIStatus.PENDING,
        }
        return mapping.get(status.lower(), CIStatus.UNKNOWN)
    
    def _parse_conclusion(self, conclusion: Optional[str]) -> Optional[CIStatus]:
        """Parse GitHub conclusion string to CIStatus enum."""
        if not conclusion:
            return None
        
        mapping = {
            "success": CIStatus.SUCCESS,
            "failure": CIStatus.FAILURE,
            "cancelled": CIStatus.CANCELLED,
            "skipped": CIStatus.SUCCESS,  # Treat skipped as success
            "neutral": CIStatus.SUCCESS,
        }
        return mapping.get(conclusion.lower(), CIStatus.FAILURE)
    
    def _parse_workflow_run(self, data: Dict[str, Any]) -> WorkflowRun:
        """Parse GitHub API response to WorkflowRun object."""
        return WorkflowRun(
            id=data["id"],
            name=data.get("name", "Unknown"),
            status=self._parse_status(data.get("status", "")),
            conclusion=self._parse_conclusion(data.get("conclusion")),
            branch=data.get("head_branch", ""),
            commit_sha=data.get("head_sha", "")[:7],
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            url=data.get("html_url", "")
        )
    
    def get_workflow_runs(
        self,
        repo_url: str,
        branch: Optional[str] = None,
        per_page: int = 10
    ) -> List[WorkflowRun]:
        """
        Get recent workflow runs for a repository.
        
        Args:
            repo_url: GitHub repository URL
            branch: Filter by branch name (optional)
            per_page: Number of runs to fetch
            
        Returns:
            List of WorkflowRun objects
        """
        repo_info = extract_repo_info(repo_url)
        if not repo_info["owner"] or not repo_info["repo"]:
            return []
        
        endpoint = f"/repos/{repo_info['owner']}/{repo_info['repo']}/actions/runs"
        params = {"per_page": per_page}
        if branch:
            params["branch"] = branch
        
        try:
            response = self.client.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            
            runs = []
            for run_data in data.get("workflow_runs", []):
                runs.append(self._parse_workflow_run(run_data))
            
            return runs
            
        except httpx.HTTPError as e:
            print(f"GitHub API error: {e}")
            return []
    
    def get_latest_run(
        self,
        repo_url: str,
        branch: str
    ) -> Optional[WorkflowRun]:
        """
        Get the latest workflow run for a specific branch.
        
        Args:
            repo_url: GitHub repository URL
            branch: Branch name to check
            
        Returns:
            Latest WorkflowRun or None
        """
        runs = self.get_workflow_runs(repo_url, branch=branch, per_page=1)
        return runs[0] if runs else None
    
    def wait_for_completion(
        self,
        repo_url: str,
        branch: str,
        timeout_seconds: int = 600,
        poll_interval: int = 15
    ) -> Optional[WorkflowRun]:
        """
        Wait for the latest workflow run to complete.
        
        Args:
            repo_url: GitHub repository URL
            branch: Branch to monitor
            timeout_seconds: Maximum time to wait
            poll_interval: Seconds between status checks
            
        Returns:
            Final WorkflowRun status or None if timeout/error
        """
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                print(f"CI monitoring timed out after {timeout_seconds}s")
                return None
            
            run = self.get_latest_run(repo_url, branch)
            
            if run is None:
                # No workflow run found yet, wait and retry
                time.sleep(poll_interval)
                continue
            
            if run.is_complete:
                return run
            
            print(f"CI status: {run.status.value} (waiting...)")
            time.sleep(poll_interval)
    
    def check_ci_status(
        self,
        repo_url: str,
        branch: str
    ) -> Dict[str, Any]:
        """
        Check current CI status and return structured result.
        
        Returns dict with:
        - status: CIStatus value
        - conclusion: Success/Failure/None
        - run_url: Link to workflow run
        - message: Human-readable status
        """
        run = self.get_latest_run(repo_url, branch)
        
        if run is None:
            return {
                "status": CIStatus.UNKNOWN.value,
                "conclusion": None,
                "run_url": None,
                "message": "No workflow runs found"
            }
        
        if run.is_complete:
            if run.is_success:
                message = "CI pipeline passed! All tests successful."
            else:
                message = f"CI pipeline failed: {run.conclusion.value if run.conclusion else 'unknown'}"
        else:
            message = f"CI pipeline {run.status.value}..."
        
        return {
            "status": run.status.value,
            "conclusion": run.conclusion.value if run.conclusion else None,
            "run_url": run.url,
            "message": message,
            "run_id": run.id,
            "commit_sha": run.commit_sha
        }


# Singleton instance
ci_monitor = CIMonitor()
