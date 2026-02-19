"""
Docker Service for Sandboxed Test Execution

Phase 3: Execute tests safely inside Docker containers with:
- No network access (--network=none)
- Memory limits (--memory=512m)
- CPU limits (--cpus=1)
- Auto-cleanup (--rm)
"""

import subprocess
import os
from typing import Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from config.settings import get_settings

settings = get_settings()


class ProjectType(str, Enum):
    PYTHON = "python"
    NODE = "node"
    UNKNOWN = "unknown"


@dataclass
class TestResult:
    """Result of a Docker test execution."""
    success: bool
    return_code: int
    stdout: str
    stderr: str
    project_type: ProjectType
    test_command: str
    duration_seconds: float = 0.0


class DockerService:
    """
    Service for running tests in sandboxed Docker containers.
    
    Security constraints enforced:
    - No network access during test runs
    - Memory and CPU limits
    - Temporary container destroyed after execution
    - No host execution
    """
    
    def __init__(self):
        self.memory_limit = settings.DOCKER_MEMORY_LIMIT
        self.cpu_limit = settings.DOCKER_CPU_LIMIT
        self.timeout = settings.DOCKER_TIMEOUT
        self.python_image = settings.PYTHON_IMAGE
        self.node_image = settings.NODE_IMAGE
    
    def detect_project_type(self, repo_dir: str) -> Tuple[ProjectType, str]:
        """
        Detect project type by checking for marker files.
        
        Returns:
            Tuple of (ProjectType, test_command)
        """
        # Check for Python project
        if os.path.exists(os.path.join(repo_dir, "requirements.txt")):
            # Check for pytest
            if os.path.exists(os.path.join(repo_dir, "pytest.ini")) or \
               os.path.exists(os.path.join(repo_dir, "pyproject.toml")) or \
               os.path.isdir(os.path.join(repo_dir, "tests")) or \
               os.path.isdir(os.path.join(repo_dir, "test")):
                return ProjectType.PYTHON, "pip install -r requirements.txt && pytest -v"
            return ProjectType.PYTHON, "pip install -r requirements.txt && python -m pytest -v"
        
        if os.path.exists(os.path.join(repo_dir, "pyproject.toml")):
            return ProjectType.PYTHON, "pip install . && pytest -v"
        
        if os.path.exists(os.path.join(repo_dir, "setup.py")):
            return ProjectType.PYTHON, "pip install -e . && pytest -v"
        
        # Check for Node.js project
        if os.path.exists(os.path.join(repo_dir, "package.json")):
            return ProjectType.NODE, "npm install && npm test"
        
        return ProjectType.UNKNOWN, ""
    
    def _build_docker_command(
        self,
        repo_dir: str,
        project_type: ProjectType,
        test_command: str
    ) -> list:
        """
        Build the Docker run command with all security constraints.
        
        Constraints:
        - --rm: Remove container after execution
        - --network=none: No network access
        - --memory: Memory limit
        - --cpus: CPU limit
        - -v: Mount repo as /app
        - -w /app: Working directory
        """
        # Select image based on project type
        if project_type == ProjectType.PYTHON:
            image = self.python_image
        elif project_type == ProjectType.NODE:
            image = self.node_image
        else:
            image = self.python_image  # Default to Python
        
        # Convert Windows path to Docker-compatible path
        repo_path = repo_dir.replace("\\", "/")
        if ":" in repo_path:
            # Windows path like D:/path -> /d/path for Docker
            drive, path = repo_path.split(":", 1)
            repo_path = f"/{drive.lower()}{path}"
        
        cmd = [
            "docker", "run",
            "--rm",                              # Auto-cleanup
            "--network=none",                    # No network access
            f"--memory={self.memory_limit}",     # Memory limit
            f"--cpus={self.cpu_limit}",          # CPU limit
            "-v", f"{repo_dir}:/app",            # Mount repo
            "-w", "/app",                        # Working directory
            image,
            "bash", "-c", test_command
        ]
        
        return cmd
    
    def run_tests(self, repo_dir: str) -> TestResult:
        """
        Run tests inside a sandboxed Docker container.
        
        Args:
            repo_dir: Path to the cloned repository
            
        Returns:
            TestResult with stdout, stderr, and success status
        """
        import time
        
        # Detect project type
        project_type, test_command = self.detect_project_type(repo_dir)
        
        if project_type == ProjectType.UNKNOWN:
            return TestResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr="Unknown project type. No requirements.txt or package.json found.",
                project_type=project_type,
                test_command=""
            )
        
        # Build Docker command
        cmd = self._build_docker_command(repo_dir, project_type, test_command)
        
        start_time = time.time()
        
        try:
            # Run Docker container
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=repo_dir
            )
            
            duration = time.time() - start_time
            
            return TestResult(
                success=result.returncode == 0,
                return_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                project_type=project_type,
                test_command=test_command,
                duration_seconds=duration
            )
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return TestResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr=f"Test execution timed out after {self.timeout} seconds",
                project_type=project_type,
                test_command=test_command,
                duration_seconds=duration
            )
        except FileNotFoundError:
            return TestResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr="Docker is not installed or not in PATH",
                project_type=project_type,
                test_command=test_command
            )
        except Exception as e:
            return TestResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr=f"Docker execution failed: {str(e)}",
                project_type=project_type,
                test_command=test_command
            )
    
    def check_docker_available(self) -> bool:
        """Check if Docker is available and running."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False


# Singleton instance
docker_service = DockerService()
