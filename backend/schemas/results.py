"""
Results Schema for Agent Run Output

Phase 9: Generate results.json with complete run information.

Includes:
- Repository and branch information
- All iterations with fixes
- Score calculation
- CI pipeline status
"""

from typing import Optional, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, computed_field

from services.error_parser import BugType


class FixStatus(str, Enum):
    """Status of an individual fix attempt."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class CIStatusResult(str, Enum):
    """Final CI pipeline status."""
    PASSING = "passing"
    FAILING = "failing"
    PENDING = "pending"
    UNKNOWN = "unknown"


class FixEntry(BaseModel):
    """Single fix entry in the results table."""
    iteration: int
    file_path: str
    line_number: int
    bug_type: str
    fix_description: str
    status: FixStatus
    commit_sha: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class IterationResult(BaseModel):
    """Result of a single iteration (retry)."""
    iteration_number: int
    tests_passed: bool
    tests_failed_count: int
    tests_passed_count: int
    errors_found: int
    fixes_applied: int
    duration_seconds: float
    fixes: List[FixEntry] = []


class AgentResults(BaseModel):
    """
    Complete results of an agent run.
    
    This is the schema for results.json as per problem statement.
    """
    # Repository info
    repo_url: str
    branch_name: str
    team_name: str
    leader_name: str
    
    # Run metadata
    run_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    
    # Summary
    total_iterations: int = 0
    total_fixes_applied: int = 0
    total_commits: int = 0
    
    # Test results
    initial_failures: int = 0
    final_failures: int = 0
    tests_passing: bool = False
    
    # CI status
    ci_status: CIStatusResult = CIStatusResult.UNKNOWN
    ci_run_url: Optional[str] = None
    
    # All iterations
    iterations: List[IterationResult] = []
    
    # Consolidated fix table
    fix_table: List[FixEntry] = []
    
    # Timing
    time_taken_seconds: float = 0.0
    
    # Error (if failed)
    error_message: Optional[str] = None
    
    @computed_field
    @property
    def score(self) -> int:
        """
        Calculate final score.
        
        Scoring rules:
        - Base score: 100 (if all tests pass)
        - Speed bonus: +10 (if completed in < 300 seconds)
        - Commit penalty: -2 per commit beyond 20
        """
        if not self.tests_passing:
            return 0
        
        base_score = 100
        
        # Speed bonus
        SPEED_BONUS_THRESHOLD = 300  # seconds
        speed_bonus = 10 if self.time_taken_seconds < SPEED_BONUS_THRESHOLD else 0
        
        # Commit penalty
        COMMIT_PENALTY_THRESHOLD = 20
        excess_commits = max(0, self.total_commits - COMMIT_PENALTY_THRESHOLD)
        commit_penalty = excess_commits * 2
        
        return max(0, base_score + speed_bonus - commit_penalty)
    
    @computed_field
    @property
    def score_breakdown(self) -> dict:
        """Detailed score breakdown."""
        if not self.tests_passing:
            return {
                "base_score": 0,
                "speed_bonus": 0,
                "commit_penalty": 0,
                "final_score": 0,
                "reason": "Tests not passing"
            }
        
        base_score = 100
        SPEED_BONUS_THRESHOLD = 300
        COMMIT_PENALTY_THRESHOLD = 20
        
        speed_bonus = 10 if self.time_taken_seconds < SPEED_BONUS_THRESHOLD else 0
        excess_commits = max(0, self.total_commits - COMMIT_PENALTY_THRESHOLD)
        commit_penalty = excess_commits * 2
        
        return {
            "base_score": base_score,
            "speed_bonus": speed_bonus,
            "commit_penalty": -commit_penalty,
            "final_score": self.score,
            "time_taken": f"{self.time_taken_seconds:.1f}s",
            "total_commits": self.total_commits
        }
    
    def to_results_json(self) -> dict:
        """Convert to results.json format as per problem statement."""
        return {
            "repo_url": self.repo_url,
            "branch_name": self.branch_name,
            "team_name": self.team_name,
            "leader_name": self.leader_name,
            "run_id": self.run_id,
            "total_failures_initial": self.initial_failures,
            "total_failures_final": self.final_failures,
            "total_fixes_applied": self.total_fixes_applied,
            "ci_status": self.ci_status.value,
            "ci_run_url": self.ci_run_url,
            "iterations": self.total_iterations,
            "time_taken_seconds": round(self.time_taken_seconds, 2),
            "score": self.score,
            "score_breakdown": self.score_breakdown,
            "fix_table": [
                {
                    "iteration": fix.iteration,
                    "file": fix.file_path,
                    "line": fix.line_number,
                    "bug_type": fix.bug_type,
                    "description": fix.fix_description,
                    "status": fix.status.value,
                    "commit": fix.commit_sha
                }
                for fix in self.fix_table
            ]
        }


class AgentResultsResponse(BaseModel):
    """API response containing agent results."""
    success: bool
    message: str
    results: Optional[AgentResults] = None
