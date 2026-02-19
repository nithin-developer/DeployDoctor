"""
CI Monitor Agent - Monitors GitHub Actions workflow runs.

This agent is responsible for:
1. Triggering workflow runs
2. Polling for workflow status
3. Fetching workflow logs
4. Detecting pass/fail states
"""

import os
import re
import time
import asyncio
import aiohttp
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from agents.base_agent import BaseAgent, AgentResult, AgentStatus


@dataclass
class WorkflowRun:
    """A GitHub Actions workflow run."""
    id: int
    name: str
    status: str  # queued, in_progress, completed
    conclusion: Optional[str]  # success, failure, cancelled, skipped
    branch: str
    commit_sha: str
    html_url: str
    created_at: str
    updated_at: str
    run_started_at: Optional[str] = None
    
    @property
    def is_completed(self) -> bool:
        return self.status == "completed"
    
    @property
    def is_success(self) -> bool:
        return self.status == "completed" and self.conclusion == "success"
    
    @property
    def is_failure(self) -> bool:
        return self.status == "completed" and self.conclusion == "failure"
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "conclusion": self.conclusion,
            "branch": self.branch,
            "commit_sha": self.commit_sha,
            "html_url": self.html_url,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "run_started_at": self.run_started_at,
            "is_completed": self.is_completed,
            "is_success": self.is_success,
            "is_failure": self.is_failure
        }


class CIMonitorAgent(BaseAgent):
    """
    Agent responsible for monitoring GitHub Actions.
    
    Uses GitHub REST API to:
    - List workflow runs
    - Get run status
    - Download logs
    """
    
    GITHUB_API_BASE = "https://api.github.com"
    
    def __init__(self, github_token: Optional[str] = None):
        super().__init__(
            name="CI Monitor Agent",
            description="I monitor GitHub Actions workflow runs.",
            use_llm=False
        )
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for GitHub API requests."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "DevOps-Agent"
        }
        if self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"
        return headers
    
    def _parse_repo_url(self, repo_url: str) -> tuple[str, str]:
        """Extract owner and repo from GitHub URL."""
        # Handle various GitHub URL formats
        patterns = [
            r'github\.com[/:]([^/]+)/([^/\.]+)',  # HTTPS or SSH
            r'^([^/]+)/([^/]+)$'  # owner/repo format
        ]
        
        for pattern in patterns:
            match = re.search(pattern, repo_url)
            if match:
                return match.group(1), match.group(2).rstrip('.git')
        
        raise ValueError(f"Could not parse GitHub URL: {repo_url}")
    
    async def list_workflow_runs(
        self,
        owner: str,
        repo: str,
        branch: Optional[str] = None,
        status: Optional[str] = None,
        per_page: int = 10
    ) -> List[WorkflowRun]:
        """List workflow runs for a repository."""
        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}/actions/runs"
        
        params = {"per_page": per_page}
        if branch:
            params["branch"] = branch
        if status:
            params["status"] = status
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, 
                headers=self._get_headers(),
                params=params
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"GitHub API error: {response.status} - {error_text}")
                
                data = await response.json()
        
        runs = []
        for run_data in data.get("workflow_runs", []):
            runs.append(WorkflowRun(
                id=run_data["id"],
                name=run_data["name"],
                status=run_data["status"],
                conclusion=run_data.get("conclusion"),
                branch=run_data["head_branch"],
                commit_sha=run_data["head_sha"],
                html_url=run_data["html_url"],
                created_at=run_data["created_at"],
                updated_at=run_data["updated_at"],
                run_started_at=run_data.get("run_started_at")
            ))
        
        return runs
    
    async def get_workflow_run(
        self,
        owner: str,
        repo: str,
        run_id: int
    ) -> WorkflowRun:
        """Get details of a specific workflow run."""
        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}/actions/runs/{run_id}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._get_headers()) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"GitHub API error: {response.status} - {error_text}")
                
                run_data = await response.json()
        
        return WorkflowRun(
            id=run_data["id"],
            name=run_data["name"],
            status=run_data["status"],
            conclusion=run_data.get("conclusion"),
            branch=run_data["head_branch"],
            commit_sha=run_data["head_sha"],
            html_url=run_data["html_url"],
            created_at=run_data["created_at"],
            updated_at=run_data["updated_at"],
            run_started_at=run_data.get("run_started_at")
        )
    
    async def get_workflow_logs(
        self,
        owner: str,
        repo: str,
        run_id: int
    ) -> str:
        """Download workflow logs."""
        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}/actions/runs/{run_id}/logs"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, 
                headers=self._get_headers(),
                allow_redirects=True
            ) as response:
                if response.status == 200:
                    # Logs are returned as a zip file
                    # For simplicity, we'll return raw content
                    content = await response.read()
                    return content.decode('utf-8', errors='replace')[:50000]
                elif response.status == 302:
                    # Follow redirect to download
                    redirect_url = response.headers.get("Location")
                    async with session.get(redirect_url) as redirect_response:
                        content = await redirect_response.read()
                        return content.decode('utf-8', errors='replace')[:50000]
                else:
                    return f"Could not fetch logs: {response.status}"
    
    async def wait_for_completion(
        self,
        owner: str,
        repo: str,
        run_id: int,
        timeout: int = 600,
        poll_interval: int = 15
    ) -> WorkflowRun:
        """Wait for a workflow run to complete."""
        start_time = time.time()
        
        while True:
            run = await self.get_workflow_run(owner, repo, run_id)
            
            if run.is_completed:
                return run
            
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(f"Workflow did not complete within {timeout}s")
            
            # Report progress
            progress = min(90, int(30 + (60 * elapsed / timeout)))
            self.report_progress(
                "waiting",
                progress,
                f"Waiting for workflow: {run.status}"
            )
            
            await asyncio.sleep(poll_interval)
    
    async def get_latest_run_for_branch(
        self,
        owner: str,
        repo: str,
        branch: str
    ) -> Optional[WorkflowRun]:
        """Get the most recent workflow run for a branch."""
        runs = await self.list_workflow_runs(
            owner, repo, 
            branch=branch, 
            per_page=1
        )
        return runs[0] if runs else None
    
    async def wait_for_new_run(
        self,
        owner: str,
        repo: str,
        branch: str,
        after_time: Optional[datetime] = None,
        timeout: int = 120,
        poll_interval: int = 10
    ) -> Optional[WorkflowRun]:
        """Wait for a new workflow run to appear after a push."""
        if not after_time:
            after_time = datetime.utcnow()
        
        start_time = time.time()
        
        while True:
            runs = await self.list_workflow_runs(owner, repo, branch=branch, per_page=5)
            
            for run in runs:
                # Parse created_at timestamp
                created = datetime.fromisoformat(run.created_at.replace('Z', '+00:00'))
                after_aware = after_time.replace(tzinfo=created.tzinfo)
                
                if created > after_aware:
                    return run
            
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                return None
            
            progress = min(90, int(10 + (80 * elapsed / timeout)))
            self.report_progress(
                "waiting",
                progress,
                "Waiting for new CI run to start"
            )
            
            await asyncio.sleep(poll_interval)
    
    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        Monitor a GitHub Actions workflow.
        
        Context should contain:
            - repo_url: GitHub repository URL
            - branch: Branch to monitor
            - action: "list", "wait", "status", or "logs"
            - run_id: (optional) Specific run ID
            - timeout: (optional) Wait timeout in seconds
        """
        start_time = time.time()
        
        repo_url = context.get("repo_url")
        branch = context.get("branch")
        action = context.get("action", "status")
        run_id = context.get("run_id")
        timeout = context.get("timeout", 600)
        
        if not repo_url:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                error="No repository URL provided"
            )
        
        try:
            owner, repo = self._parse_repo_url(repo_url)
        except ValueError as e:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                error=str(e)
            )
        
        try:
            if action == "list":
                self.report_progress("listing", 50, "Listing workflow runs")
                runs = await self.list_workflow_runs(owner, repo, branch=branch)
                
                return AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.SUCCESS,
                    data={
                        "runs": [r.to_dict() for r in runs],
                        "count": len(runs)
                    },
                    duration_seconds=time.time() - start_time
                )
            
            elif action == "status":
                if run_id:
                    self.report_progress("fetching", 50, "Fetching run status")
                    run = await self.get_workflow_run(owner, repo, run_id)
                else:
                    self.report_progress("fetching", 50, "Fetching latest run")
                    run = await self.get_latest_run_for_branch(owner, repo, branch)
                    
                    if not run:
                        return AgentResult(
                            agent_name=self.name,
                            status=AgentStatus.FAILED,
                            error=f"No workflow runs found for branch: {branch}"
                        )
                
                return AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.SUCCESS,
                    data={
                        "run": run.to_dict(),
                        "is_success": run.is_success,
                        "is_failure": run.is_failure
                    },
                    duration_seconds=time.time() - start_time
                )
            
            elif action == "wait":
                if not run_id and not branch:
                    return AgentResult(
                        agent_name=self.name,
                        status=AgentStatus.FAILED,
                        error="Either run_id or branch required for wait action"
                    )
                
                if not run_id:
                    # Get latest run for branch
                    latest = await self.get_latest_run_for_branch(owner, repo, branch)
                    if not latest:
                        return AgentResult(
                            agent_name=self.name,
                            status=AgentStatus.FAILED,
                            error=f"No workflow runs found for branch: {branch}"
                        )
                    run_id = latest.id
                
                self.report_progress("waiting", 30, "Waiting for completion")
                run = await self.wait_for_completion(
                    owner, repo, run_id, 
                    timeout=timeout
                )
                
                return AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.SUCCESS,
                    data={
                        "run": run.to_dict(),
                        "is_success": run.is_success,
                        "is_failure": run.is_failure
                    },
                    duration_seconds=time.time() - start_time
                )
            
            elif action == "logs":
                if not run_id:
                    return AgentResult(
                        agent_name=self.name,
                        status=AgentStatus.FAILED,
                        error="run_id required for logs action"
                    )
                
                self.report_progress("fetching", 50, "Downloading logs")
                logs = await self.get_workflow_logs(owner, repo, run_id)
                
                return AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.SUCCESS,
                    data={
                        "logs": logs,
                        "run_id": run_id
                    },
                    duration_seconds=time.time() - start_time
                )
            
            else:
                return AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.FAILED,
                    error=f"Unknown action: {action}"
                )
                
        except Exception as e:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                error=str(e),
                duration_seconds=time.time() - start_time
            )
