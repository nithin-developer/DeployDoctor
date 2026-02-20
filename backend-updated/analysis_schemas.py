from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class BugType(str, Enum):
    LINTING = "LINTING"
    SYNTAX = "SYNTAX"
    LOGIC = "LOGIC"
    TYPE_ERROR = "TYPE_ERROR"
    IMPORT = "IMPORT"
    INDENTATION = "INDENTATION"
    TEST_FAILURE = "TEST_FAILURE"
    RUNTIME = "RUNTIME"
    DOCKER_ERROR = "DOCKER_ERROR"


class FixStatus(str, Enum):
    FIXED = "FIXED"
    FAILED = "FAILED"


class CIStatusEnum(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"


class AnalysisRequest(BaseModel):
    repo_url: str
    team_name: str
    team_leader_name: str
    github_token: Optional[str] = None  # PAT for pushing fixes to branch
    generate_tests: bool = True  # Whether to generate test cases
    push_to_github: bool = True  # Whether to push fixes to GitHub
    create_pr: bool = True  # Whether to create a PR after pushing
    auto_merge_on_ci_success: bool = True  # Auto-merge when CI passes


class CodeFix(BaseModel):
    file_path: str
    bug_type: BugType
    line_number: int
    commit_message: str
    status: FixStatus
    original_code: Optional[str] = None
    fixed_code: Optional[str] = None
    description: Optional[str] = None


class TestResult(BaseModel):
    test_name: str
    passed: bool
    error_message: Optional[str] = None
    duration: Optional[float] = None
    file_path: Optional[str] = None  # File where test failed
    line_number: Optional[int] = None  # Line number of failure
    failure_type: Optional[str] = None  # Type of failure (AssertionError, etc.)


class AnalysisResult(BaseModel):
    repo_url: str
    team_name: str
    team_leader_name: str
    branch_name: str
    total_failures_detected: int
    total_fixes_applied: int
    total_time_taken: float
    fixes: List[CodeFix]
    test_results: List[TestResult]
    start_time: datetime
    end_time: datetime
    status: str = "completed"
    summary: Optional[Dict[str, Any]] = None  # Detailed analysis summary with iterations
    generated_tests: Optional[List[Dict[str, Any]]] = None  # AI-generated test cases
    commit_sha: Optional[str] = None  # Commit SHA after pushing to GitHub
    branch_url: Optional[str] = None  # URL to the created branch
    commit_message: Optional[str] = None  # Full commit message used
    # PR and CI fields
    pr_url: Optional[str] = None  # URL to the created PR
    pr_number: Optional[int] = None  # PR number
    ci_status: Optional[CIStatusEnum] = None  # CI workflow status
    merged: bool = False  # Whether PR was merged


class GeneratedTest(BaseModel):
    """AI-generated test case"""
    file_path: str  # Path to test file
    test_name: str  # Name of the test
    test_code: str  # Full test code
    target_file: str  # File being tested
    target_function: Optional[str] = None  # Function being tested
    test_framework: str = "pytest"  # pytest or unittest


class AnalysisStatus(BaseModel):
    status: str
    progress: int
    current_step: str
    message: str
