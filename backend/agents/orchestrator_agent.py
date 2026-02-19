"""
Orchestrator Agent - Main coordination agent for CI/CD healing.

This agent orchestrates the full autonomous loop:
1. Clone repository
2. Run tests in sandbox
3. Parse errors
4. Generate and apply fixes
5. Commit and push
6. Monitor CI
7. Repeat until success or max retries
"""

import os
import time
import asyncio
import subprocess
import shutil
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

from agents.base_agent import BaseAgent, AgentResult, AgentStatus
from agents.sandbox_executor_agent import SandboxExecutorAgent
from agents.error_parser_agent import ErrorParserAgent
from agents.code_fixer_agent import CodeFixerAgent
from agents.test_runner_agent import TestRunnerAgent
from agents.ci_monitor_agent import CIMonitorAgent


@dataclass
class IterationResult:
    """Result of a single fix iteration."""
    iteration: int
    success: bool
    errors_found: int
    fixes_applied: int
    commit_sha: Optional[str]
    ci_passed: Optional[bool]
    duration_seconds: float
    message: str
    
    def to_dict(self) -> Dict:
        return {
            "iteration": self.iteration,
            "success": self.success,
            "errors_found": self.errors_found,
            "fixes_applied": self.fixes_applied,
            "commit_sha": self.commit_sha,
            "ci_passed": self.ci_passed,
            "duration_seconds": self.duration_seconds,
            "message": self.message
        }


@dataclass
class OrchestratorResult:
    """Full result of the orchestration process."""
    success: bool
    total_iterations: int
    total_fixes: int
    total_commits: int
    total_duration_seconds: float
    branch_name: str
    final_status: str
    iterations: List[IterationResult] = field(default_factory=list)
    score: Optional[int] = None
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "total_iterations": self.total_iterations,
            "total_fixes": self.total_fixes,
            "total_commits": self.total_commits,
            "total_duration_seconds": self.total_duration_seconds,
            "branch_name": self.branch_name,
            "final_status": self.final_status,
            "iterations": [i.to_dict() for i in self.iterations],
            "score": self.score
        }


class OrchestratorAgent(BaseAgent):
    """
    Main orchestrator agent that coordinates all other agents.
    
    Runs the autonomous CI/CD healing loop:
    1. Clone repo and create branch
    2. Run tests locally
    3. Parse errors
    4. Fix errors with AI
    5. Commit and push
    6. Monitor CI
    7. Repeat until success or max retries
    """
    
    MAX_ITERATIONS = 5
    WORK_DIR = Path("./temp_repos")
    BASE_SCORE = 100
    SPEED_BONUS_THRESHOLD = 300  # seconds
    SPEED_BONUS = 10
    COMMIT_PENALTY_THRESHOLD = 20
    COMMIT_PENALTY = 2
    
    def __init__(
        self,
        github_token: Optional[str] = None,
        on_progress: Optional[Callable] = None
    ):
        super().__init__(
            name="Orchestrator Agent",
            description="I coordinate the full CI/CD healing process.",
            use_llm=False
        )
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
        self.external_progress = on_progress
        
        # Initialize sub-agents
        self.sandbox_agent = SandboxExecutorAgent()
        self.error_parser = ErrorParserAgent()
        self.code_fixer = CodeFixerAgent()
        self.test_runner = TestRunnerAgent()
        self.ci_monitor = CIMonitorAgent(github_token=self.github_token)
    
    def report_progress(
        self, 
        stage: str, 
        percent: int, 
        message: str
    ):
        """Report progress to both base class and external callback."""
        super().report_progress(stage, percent, message)
        if self.external_progress:
            try:
                self.external_progress(stage, percent, message)
            except Exception:
                pass
    
    async def clone_repository(
        self, 
        repo_url: str, 
        branch: str,
        work_dir: Path
    ) -> Path:
        """Clone a repository and checkout branch."""
        # Create work directory
        work_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique repo directory
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        timestamp = int(time.time())
        repo_dir = work_dir / f"{repo_name}_{timestamp}"
        
        # Clone with authentication
        if self.github_token and "github.com" in repo_url:
            # Insert token into URL
            if repo_url.startswith("https://"):
                auth_url = repo_url.replace(
                    "https://", 
                    f"https://{self.github_token}@"
                )
            else:
                auth_url = repo_url
        else:
            auth_url = repo_url
        
        # Clone
        result = subprocess.run(
            ["git", "clone", auth_url, str(repo_dir)],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise Exception(f"Clone failed: {result.stderr}")
        
        # Checkout or create branch
        result = subprocess.run(
            ["git", "checkout", "-B", branch],
            cwd=str(repo_dir),
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise Exception(f"Branch checkout failed: {result.stderr}")
        
        return repo_dir
    
    async def commit_and_push(
        self,
        repo_dir: Path,
        branch: str,
        message: str
    ) -> Optional[str]:
        """Commit changes and push to remote."""
        # Configure git
        subprocess.run(
            ["git", "config", "user.email", "ai-agent@devops.local"],
            cwd=str(repo_dir),
            capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "AI DevOps Agent"],
            cwd=str(repo_dir),
            capture_output=True
        )
        
        # Stage all changes
        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(repo_dir),
            capture_output=True
        )
        
        # Check if there are changes
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True
        )
        
        if not status.stdout.strip():
            return None  # No changes to commit
        
        # Commit
        commit_result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(repo_dir),
            capture_output=True,
            text=True
        )
        
        if commit_result.returncode != 0:
            return None
        
        # Get commit SHA
        sha_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True
        )
        commit_sha = sha_result.stdout.strip()[:8]
        
        # Push
        push_result = subprocess.run(
            ["git", "push", "-u", "origin", branch, "--force"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True
        )
        
        if push_result.returncode != 0:
            raise Exception(f"Push failed: {push_result.stderr}")
        
        return commit_sha
    
    def calculate_score(
        self,
        success: bool,
        duration_seconds: float,
        total_commits: int,
        total_fixes: int = 0
    ) -> int:
        """Calculate the final score."""
        # Base score depends on success
        if success:
            score = self.BASE_SCORE
        elif total_fixes > 0:
            # Partial success - give partial credit
            score = min(self.BASE_SCORE, 40 + (total_fixes * 15))
        else:
            return 0
        
        # Speed bonus (only for full success)
        if success and duration_seconds < self.SPEED_BONUS_THRESHOLD:
            score += self.SPEED_BONUS
        
        # Commit penalty
        if total_commits > self.COMMIT_PENALTY_THRESHOLD:
            penalty = (total_commits - self.COMMIT_PENALTY_THRESHOLD) * self.COMMIT_PENALTY
            score -= penalty
        
        return max(0, score)
    
    def generate_branch_name(
        self,
        team_name: str,
        leader_name: str
    ) -> str:
        """Generate branch name in required format."""
        # Clean names
        team_clean = team_name.replace(" ", "_").upper()
        leader_clean = leader_name.replace(" ", "_")
        return f"{team_clean}_{leader_clean}_AI_Fix"
    
    async def run_iteration(
        self,
        repo_dir: Path,
        repo_url: str,
        branch: str,
        iteration: int
    ) -> IterationResult:
        """Run a single fix iteration."""
        start_time = time.time()
        
        self.report_progress(
            "iteration",
            int(10 + (iteration * 15)),
            f"Starting iteration {iteration + 1}"
        )
        
        # Run tests locally
        self.report_progress(
            "testing",
            int(15 + (iteration * 15)),
            "Running tests"
        )
        
        sandbox_result = await self.sandbox_agent.execute({
            "repo_path": str(repo_dir)
        })
        
        # Check if tests passed (all checks succeeded)
        if sandbox_result.status == AgentStatus.SUCCESS:
            failed_count = sandbox_result.data.get("failed", 0)
            if failed_count == 0:
                return IterationResult(
                    iteration=iteration + 1,
                    success=True,
                    errors_found=0,
                    fixes_applied=0,
                    commit_sha=None,
                    ci_passed=True,
                    duration_seconds=time.time() - start_time,
                    message="All tests passing"
                )
        
        # Collect output from all results for parsing
        output_parts = []
        all_results = sandbox_result.data.get("all_results", []) if sandbox_result.data else []
        for res in all_results:
            if res.get("stderr"):
                output_parts.append(res["stderr"])
            if res.get("stdout"):
                output_parts.append(res["stdout"])
        
        # Also use pre-parsed errors from sandbox if available
        sandbox_errors = sandbox_result.data.get("errors", []) if sandbox_result.data else []
        output = "\n".join(output_parts) if output_parts else (sandbox_result.error or "")
        
        # Parse errors
        self.report_progress(
            "parsing",
            int(25 + (iteration * 15)),
            "Parsing errors"
        )
        
        # Use sandbox errors if available, otherwise parse output
        errors = []
        if sandbox_errors:
            # Convert sandbox errors to parser format
            for err in sandbox_errors:
                errors.append({
                    "file_path": err.get("file", ""),
                    "line_number": err.get("line", 0),
                    "message": err.get("message", err.get("stderr", "Unknown error")),
                    "error_type": err.get("type", "ERROR"),
                    "bug_type": "SYNTAX" if "Syntax" in str(err.get("type", "")) else "UNKNOWN"
                })
        
        if not errors and output:
            # Detect project type from sandbox
            project_type = sandbox_result.data.get("project_type", "python") if sandbox_result.data else "python"
            
            parse_result = await self.error_parser.execute({
                "output": output,
                "project_type": project_type
            })
            
            if parse_result.status == AgentStatus.SUCCESS:
                errors = parse_result.data.get("errors", [])
        
        if not errors:
            return IterationResult(
                iteration=iteration + 1,
                success=True,  # No errors means success!
                errors_found=0,
                fixes_applied=0,
                commit_sha=None,
                ci_passed=True,
                duration_seconds=time.time() - start_time,
                message="All errors fixed"
            )
        
        # Generate and apply fixes
        self.report_progress(
            "fixing",
            int(40 + (iteration * 15)),
            f"Fixing {len(errors)} errors"
        )
        
        fix_result = await self.code_fixer.execute({
            "repo_path": str(repo_dir),
            "errors": errors,
            "apply_fixes": True,
            "max_fixes": 5
        })
        
        fixes_applied = 0
        if fix_result.status == AgentStatus.SUCCESS:
            fixes_applied = fix_result.data.get("fixes_applied", 0)
        
        if fixes_applied == 0:
            return IterationResult(
                iteration=iteration + 1,
                success=False,
                errors_found=len(errors),
                fixes_applied=0,
                commit_sha=None,
                ci_passed=False,
                duration_seconds=time.time() - start_time,
                message="Could not apply any fixes"
            )
        
        # Commit and push
        self.report_progress(
            "committing",
            int(60 + (iteration * 10)),
            "Committing changes"
        )
        
        # Build commit message
        primary_error = errors[0] if errors else {}
        bug_type = primary_error.get("bug_type", "UNKNOWN")
        file_path = primary_error.get("file_path", "unknown")
        line_num = primary_error.get("line_number", 0)
        
        commit_message = f"[AI-AGENT] Fix {bug_type} in {file_path} line {line_num}"
        
        try:
            commit_sha = await self.commit_and_push(repo_dir, branch, commit_message)
        except Exception as e:
            return IterationResult(
                iteration=iteration + 1,
                success=False,
                errors_found=len(errors),
                fixes_applied=fixes_applied,
                commit_sha=None,
                ci_passed=None,
                duration_seconds=time.time() - start_time,
                message=f"Push failed: {str(e)}"
            )
        
        # Monitor CI
        self.report_progress(
            "monitoring",
            int(75 + (iteration * 5)),
            "Waiting for CI"
        )
        
        ci_passed = None
        try:
            # Wait for new CI run to appear
            ci_result = await self.ci_monitor.execute({
                "repo_url": repo_url,
                "branch": branch,
                "action": "wait",
                "timeout": 300
            })
            
            if ci_result.status == AgentStatus.SUCCESS:
                ci_passed = ci_result.data.get("is_success", False)
        except Exception as e:
            # CI monitoring is optional
            ci_passed = None
        
        return IterationResult(
            iteration=iteration + 1,
            success=ci_passed == True,
            errors_found=len(errors),
            fixes_applied=fixes_applied,
            commit_sha=commit_sha,
            ci_passed=ci_passed,
            duration_seconds=time.time() - start_time,
            message="Iteration complete"
        )
    
    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        Execute the full CI/CD healing process.
        
        Context should contain:
            - repo_url: GitHub repository URL
            - team_name: Team name for branch naming
            - leader_name: Leader name for branch naming
            - max_iterations: (optional) Max fix attempts
            - skip_ci: (optional) Skip CI monitoring
        """
        start_time = time.time()
        
        repo_url = context.get("repo_url")
        team_name = context.get("team_name", "Team")
        leader_name = context.get("leader_name", "Leader")
        max_iterations = context.get("max_iterations", self.MAX_ITERATIONS)
        skip_ci = context.get("skip_ci", False)
        
        if not repo_url:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                error="No repository URL provided"
            )
        
        # Generate branch name
        branch_name = self.generate_branch_name(team_name, leader_name)
        
        # Clone repository
        self.report_progress("cloning", 5, "Cloning repository")
        
        repo_dir = None
        try:
            repo_dir = await self.clone_repository(
                repo_url, 
                branch_name, 
                self.WORK_DIR
            )
        except Exception as e:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                error=f"Clone failed: {str(e)}"
            )
        
        iterations = []
        total_fixes = 0
        total_commits = 0
        final_success = False
        
        try:
            for i in range(max_iterations):
                result = await self.run_iteration(
                    repo_dir, 
                    repo_url, 
                    branch_name, 
                    i
                )
                
                iterations.append(result)
                total_fixes += result.fixes_applied
                if result.commit_sha:
                    total_commits += 1
                
                # Check for success
                if result.success:
                    final_success = True
                    break
                
                # If no fixes applied three times in a row, give up
                if i >= 2:
                    recent = iterations[-3:]
                    if all(r.fixes_applied == 0 for r in recent):
                        break
            
        finally:
            # Cleanup
            if repo_dir and repo_dir.exists():
                try:
                    shutil.rmtree(repo_dir)
                except Exception:
                    pass
        
        total_duration = time.time() - start_time
        
        # Calculate score
        score = self.calculate_score(
            final_success,
            total_duration,
            total_commits,
            total_fixes
        )
        
        # Determine final status
        if final_success:
            final_status = "SUCCESS"
        elif total_fixes > 0:
            final_status = "PARTIAL"
        else:
            final_status = "FAILED"
        
        orchestrator_result = OrchestratorResult(
            success=final_success,
            total_iterations=len(iterations),
            total_fixes=total_fixes,
            total_commits=total_commits,
            total_duration_seconds=total_duration,
            branch_name=branch_name,
            final_status=final_status,
            iterations=iterations,
            score=score
        )
        
        self.report_progress("complete", 100, final_status)
        
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS if final_success else AgentStatus.FAILED,
            data=orchestrator_result.to_dict(),
            duration_seconds=total_duration
        )
