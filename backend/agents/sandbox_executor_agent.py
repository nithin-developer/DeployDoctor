"""
Sandbox Executor Agent - Runs code in Docker containers for safe execution.

This agent is responsible for:
1. Detecting project type (Python, Node.js, etc.)
2. Running code in isolated Docker containers
3. Capturing stdout, stderr, and exit codes
4. Parsing runtime errors
"""

import os
import asyncio
import subprocess
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path

from agents.base_agent import BaseAgent, AgentResult, AgentStatus
from config.settings import get_settings

settings = get_settings()


@dataclass
class ExecutionResult:
    """Result of code execution in sandbox."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    error_file: Optional[str] = None
    error_line: Optional[int] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class SandboxExecutorAgent(BaseAgent):
    """
    Agent responsible for running code in a sandboxed Docker environment.
    
    Features:
    - Detects project type automatically
    - Runs tests in isolated Docker containers
    - Enforces resource limits (memory, CPU)
    - No network access for security
    - Captures detailed error information
    """
    
    def __init__(self):
        super().__init__(
            name="Sandbox Executor Agent",
            description="I run code in isolated Docker containers to detect runtime errors safely.",
            use_llm=False  # This agent doesn't need LLM
        )
        self.docker_available = self._check_docker()
    
    def _check_docker(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ['docker', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def detect_project_type(self, repo_path: str) -> str:
        """
        Detect the type of project based on files present.
        
        Returns: 'python', 'node', or 'unknown'
        """
        repo_path = Path(repo_path)
        
        # Python indicators
        python_indicators = [
            'requirements.txt', 'pyproject.toml', 'setup.py',
            'Pipfile', 'poetry.lock', 'setup.cfg'
        ]
        for indicator in python_indicators:
            if (repo_path / indicator).exists():
                return 'python'
        
        # Node.js indicators
        node_indicators = [
            'package.json', 'package-lock.json', 
            'yarn.lock', 'pnpm-lock.yaml'
        ]
        for indicator in node_indicators:
            if (repo_path / indicator).exists():
                return 'node'
        
        # Check file extensions
        for f in repo_path.iterdir():
            if f.is_file():
                if f.suffix == '.py':
                    return 'python'
                if f.suffix in ['.js', '.ts', '.jsx', '.tsx']:
                    return 'node'
        
        return 'unknown'
    
    def _find_entry_points(self, repo_path: str, project_type: str) -> List[str]:
        """Find entry point files for execution."""
        repo_path = Path(repo_path)
        entry_points = []
        
        if project_type == 'python':
            # Common Python entry points
            common = ['main.py', 'app.py', 'run.py', '__main__.py', 'server.py', 'index.py']
            for name in common:
                if (repo_path / name).exists():
                    entry_points.append(name)
            
            # If none found, look for any Python files
            if not entry_points:
                for f in repo_path.iterdir():
                    if f.suffix == '.py' and not f.name.startswith('test_') and not f.name.startswith('_'):
                        entry_points.append(f.name)
        
        elif project_type == 'node':
            # Check package.json for main
            pkg_json = repo_path / 'package.json'
            if pkg_json.exists():
                import json
                try:
                    with open(pkg_json) as f:
                        pkg = json.load(f)
                        main = pkg.get('main', 'index.js')
                        if (repo_path / main).exists():
                            entry_points.append(main)
                except:
                    pass
            
            # Common Node entry points
            common = ['index.js', 'app.js', 'server.js', 'main.js']
            for name in common:
                if (repo_path / name).exists() and name not in entry_points:
                    entry_points.append(name)
        
        return entry_points[:3]  # Limit to 3
    
    async def _run_python_syntax_check(self, repo_path: str) -> List[ExecutionResult]:
        """Check Python syntax for all files."""
        results = []
        repo_path = Path(repo_path)
        
        for py_file in repo_path.rglob('*.py'):
            if '__pycache__' in str(py_file) or '.venv' in str(py_file):
                continue
            
            try:
                relative_path = py_file.relative_to(repo_path)
                process = await asyncio.create_subprocess_exec(
                    'python', '-m', 'py_compile', str(py_file),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=10
                )
                
                if process.returncode != 0:
                    error_info = self._parse_python_error(stderr.decode())
                    results.append(ExecutionResult(
                        success=False,
                        stdout=stdout.decode(),
                        stderr=stderr.decode(),
                        exit_code=process.returncode,
                        error_file=str(relative_path),
                        error_line=error_info.get('line'),
                        error_type=error_info.get('type', 'SyntaxError'),
                        error_message=error_info.get('message')
                    ))
            except asyncio.TimeoutError:
                results.append(ExecutionResult(
                    success=False,
                    stdout="",
                    stderr="Syntax check timed out",
                    exit_code=-1,
                    error_type="TIMEOUT"
                ))
            except Exception as e:
                results.append(ExecutionResult(
                    success=False,
                    stdout="",
                    stderr=str(e),
                    exit_code=-1,
                    error_type="ERROR"
                ))
        
        return results
    
    def _parse_python_error(self, stderr: str) -> Dict:
        """Parse Python error output to extract file, line, and message."""
        import re
        
        # Pattern: File "path", line X
        file_line_match = re.search(r'File "([^"]+)", line (\d+)', stderr)
        
        # Pattern: ErrorType: message
        error_match = re.search(r'(\w+Error|\w+Exception): (.+)', stderr)
        
        result = {}
        
        if file_line_match:
            result['file'] = file_line_match.group(1)
            result['line'] = int(file_line_match.group(2))
        
        if error_match:
            result['type'] = error_match.group(1)
            result['message'] = error_match.group(2).strip()
        
        return result
    
    async def _run_in_docker(
        self, 
        repo_path: str, 
        project_type: str,
        command: List[str]
    ) -> ExecutionResult:
        """Run command in Docker container with resource limits."""
        
        # Select image based on project type
        image = settings.PYTHON_IMAGE if project_type == 'python' else settings.NODE_IMAGE
        
        # Build Docker command with security constraints
        docker_cmd = [
            'docker', 'run',
            '--rm',  # Remove container after exit
            '--network', 'none',  # No network access
            '--memory', settings.DOCKER_MEMORY_LIMIT,
            f'--cpus={settings.DOCKER_CPU_LIMIT}',
            '-v', f'{repo_path}:/app:ro',  # Mount repo read-only
            '-w', '/app',
            image
        ] + command
        
        try:
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=settings.DOCKER_TIMEOUT
            )
            
            error_info = {}
            if process.returncode != 0:
                error_info = self._parse_python_error(stderr.decode())
            
            return ExecutionResult(
                success=process.returncode == 0,
                stdout=stdout.decode(),
                stderr=stderr.decode(),
                exit_code=process.returncode,
                error_file=error_info.get('file'),
                error_line=error_info.get('line'),
                error_type=error_info.get('type'),
                error_message=error_info.get('message')
            )
            
        except asyncio.TimeoutError:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Execution timed out after {settings.DOCKER_TIMEOUT}s",
                exit_code=-1,
                error_type="TIMEOUT"
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                error_type="DOCKER_ERROR"
            )
    
    async def _run_subprocess(
        self, 
        repo_path: str,
        command: List[str]
    ) -> ExecutionResult:
        """Run command as subprocess (fallback when Docker unavailable)."""
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60  # 1 minute timeout
            )
            
            error_info = {}
            if process.returncode != 0:
                error_info = self._parse_python_error(stderr.decode())
            
            return ExecutionResult(
                success=process.returncode == 0,
                stdout=stdout.decode(),
                stderr=stderr.decode(),
                exit_code=process.returncode,
                error_file=error_info.get('file'),
                error_line=error_info.get('line'),
                error_type=error_info.get('type'),
                error_message=error_info.get('message')
            )
            
        except asyncio.TimeoutError:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="Execution timed out",
                exit_code=-1,
                error_type="TIMEOUT"
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                error_type="ERROR"
            )
    
    async def run_tests(self, repo_path: str, project_type: str) -> List[ExecutionResult]:
        """
        Run tests for the project.
        
        Returns list of execution results.
        """
        results = []
        
        if project_type == 'python':
            # First run syntax check
            syntax_results = await self._run_python_syntax_check(repo_path)
            results.extend(syntax_results)
            
            # Then run pytest if available
            test_cmd = ['python', '-m', 'pytest', '-v', '--tb=short']
            
            if self.docker_available:
                test_result = await self._run_in_docker(repo_path, project_type, test_cmd)
            else:
                test_result = await self._run_subprocess(repo_path, test_cmd)
            
            results.append(test_result)
            
        elif project_type == 'node':
            # Run npm test
            test_cmd = ['npm', 'test']
            
            if self.docker_available:
                # Need to install deps first
                install_result = await self._run_in_docker(
                    repo_path, project_type, ['npm', 'install']
                )
                if install_result.success:
                    test_result = await self._run_in_docker(repo_path, project_type, test_cmd)
                    results.append(test_result)
                else:
                    results.append(install_result)
            else:
                test_result = await self._run_subprocess(repo_path, test_cmd)
                results.append(test_result)
        
        return results
    
    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        Execute sandbox tests.
        
        Context should contain:
            - repo_path: Path to the repository
            - project_type: (optional) Type of project
        """
        start_time = time.time()
        repo_path = context.get("repo_path")
        
        if not repo_path:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                error="No repository path provided"
            )
        
        if not os.path.exists(repo_path):
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                error=f"Repository path does not exist: {repo_path}"
            )
        
        # Detect project type if not provided
        project_type = context.get("project_type") or self.detect_project_type(repo_path)
        
        self.report_progress("running", 10, f"Detected project type: {project_type}")
        
        if project_type == 'unknown':
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                data={"project_type": "unknown"},
                error="Could not detect project type. No Python or Node.js files found."
            )
        
        self.report_progress("running", 20, "Running tests in sandbox...")
        
        # Run tests
        results = await self.run_tests(repo_path, project_type)
        
        # Count successes and failures
        total = len(results)
        passed = sum(1 for r in results if r.success)
        failed = total - passed
        
        # Collect errors
        errors = []
        for r in results:
            if not r.success and r.error_file:
                errors.append({
                    "file": r.error_file,
                    "line": r.error_line,
                    "type": r.error_type,
                    "message": r.error_message,
                    "stderr": r.stderr[:500] if r.stderr else None
                })
        
        duration = time.time() - start_time
        
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS if failed == 0 else AgentStatus.FAILED,
            data={
                "project_type": project_type,
                "docker_available": self.docker_available,
                "total_checks": total,
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "all_results": [
                    {
                        "success": r.success,
                        "exit_code": r.exit_code,
                        "error_type": r.error_type,
                        "error_file": r.error_file,
                        "error_line": r.error_line,
                        "stdout": r.stdout[:1000] if r.stdout else None,
                        "stderr": r.stderr[:1000] if r.stderr else None
                    }
                    for r in results
                ]
            },
            duration_seconds=duration
        )
