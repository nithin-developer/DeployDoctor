import re
from typing import Optional, List
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, field_validator


class ProjectType(str, Enum):
    PYTHON = "python"
    NODE = "node"
    UNKNOWN = "unknown"


class AgentStatus(str, Enum):
    PENDING = "pending"
    CLONING = "cloning"
    BRANCHING = "branching"
    ANALYZING = "analyzing"
    TESTING = "testing"
    FIXING = "fixing"
    COMPLETED = "completed"
    FAILED = "failed"


# ============ REQUEST SCHEMAS ============

class AgentRequest(BaseModel):
    repo_url: str
    team_name: str
    leader_name: str

    @field_validator('repo_url')
    @classmethod
    def validate_repo_url(cls, v: str) -> str:
        """Validate that repo_url is a valid GitHub URL"""
        v = v.strip()
        github_pattern = r'^https?://github\.com/[\w\-]+/[\w\-\.]+(?:\.git)?/?$'
        if not re.match(github_pattern, v):
            raise ValueError('Invalid GitHub repository URL. Must be in format: https://github.com/owner/repo')
        return v

    @field_validator('team_name')
    @classmethod
    def validate_team_name(cls, v: str) -> str:
        """Validate team name is provided and clean"""
        v = v.strip()
        if not v:
            raise ValueError('Team name is required')
        if len(v) < 2:
            raise ValueError('Team name must be at least 2 characters')
        if len(v) > 50:
            raise ValueError('Team name must not exceed 50 characters')
        return v

    @field_validator('leader_name')
    @classmethod
    def validate_leader_name(cls, v: str) -> str:
        """Validate leader name is provided and clean"""
        v = v.strip()
        if not v:
            raise ValueError('Leader name is required')
        if len(v) < 2:
            raise ValueError('Leader name must be at least 2 characters')
        if len(v) > 50:
            raise ValueError('Leader name must not exceed 50 characters')
        return v


# ============ RESPONSE SCHEMAS ============

class AgentRunLog(BaseModel):
    timestamp: datetime
    status: AgentStatus
    message: str


class AgentResponse(BaseModel):
    success: bool
    message: str
    run_id: Optional[str] = None
    branch_name: Optional[str] = None
    repo_url: Optional[str] = None
    team_name: Optional[str] = None
    leader_name: Optional[str] = None
    project_type: Optional[ProjectType] = None
    temp_dir: Optional[str] = None
    status: AgentStatus = AgentStatus.PENDING
    logs: List[AgentRunLog] = []
    error: Optional[str] = None
    # Results from the full agent run
    results_json: Optional[dict] = None


class BranchNameResponse(BaseModel):
    branch_name: str
    team_name: str
    leader_name: str


class RepoValidationResponse(BaseModel):
    valid: bool
    url: str
    message: Optional[str] = None
    error: Optional[str] = None


class ProjectDetectionResponse(BaseModel):
    project_type: ProjectType
    detected_files: List[str]
    has_tests: bool
    test_command: Optional[str] = None
