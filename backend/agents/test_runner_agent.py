"""
Test Runner Agent - Discovers and runs tests in a repository.

This agent is responsible for:
1. Detecting test frameworks (pytest, jest, vitest, mocha)
2. Discovering test files
3. Running tests through sandbox or directly
4. Reporting test results
"""

import os
import re
import time
import asyncio
import subprocess
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from agents.base_agent import BaseAgent, AgentResult, AgentStatus


@dataclass
class TestResult:
    """Result of a test run."""
    framework: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    total: int = 0
    duration_seconds: float = 0.0
    output: str = ""
    success: bool = False
    failed_tests: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "framework": self.framework,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
            "total": self.total,
            "duration_seconds": self.duration_seconds,
            "output": self.output[:5000],  # Truncate long output
            "success": self.success,
            "failed_tests": self.failed_tests
        }


class TestRunnerAgent(BaseAgent):
    """
    Agent responsible for running tests.
    
    Supports:
    - Python: pytest, unittest
    - Node.js: jest, vitest, mocha
    """
    
    # Test file patterns by framework
    TEST_PATTERNS = {
        "pytest": ["test_*.py", "*_test.py", "tests/*.py"],
        "jest": ["*.test.js", "*.test.jsx", "*.test.ts", "*.test.tsx", "__tests__/**/*.js"],
        "vitest": ["*.test.js", "*.test.ts", "*.spec.js", "*.spec.ts"],
        "mocha": ["test/**/*.js", "test/**/*.ts"]
    }
    
    # Commands to run tests
    TEST_COMMANDS = {
        "pytest": "python -m pytest -v --tb=short 2>&1",
        "unittest": "python -m unittest discover -v 2>&1",
        "jest": "npx jest --verbose 2>&1",
        "vitest": "npx vitest run --reporter=verbose 2>&1",
        "mocha": "npx mocha --reporter spec 2>&1"
    }
    
    def __init__(self):
        super().__init__(
            name="Test Runner Agent",
            description="I discover and run tests in repositories.",
            use_llm=False
        )
    
    def detect_test_framework(self, repo_path: Path) -> Optional[str]:
        """Detect the test framework used in the repository."""
        # Check package.json for JS frameworks
        package_json = repo_path / "package.json"
        if package_json.exists():
            try:
                import json
                data = json.loads(package_json.read_text(encoding='utf-8'))
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                
                if "vitest" in deps:
                    return "vitest"
                if "jest" in deps:
                    return "jest"
                if "mocha" in deps:
                    return "mocha"
            except Exception:
                pass
        
        # Check for pytest
        pytest_ini = repo_path / "pytest.ini"
        pyproject = repo_path / "pyproject.toml"
        setup_cfg = repo_path / "setup.cfg"
        
        if pytest_ini.exists():
            return "pytest"
        
        if pyproject.exists():
            content = pyproject.read_text(encoding='utf-8')
            if "pytest" in content:
                return "pytest"
        
        if setup_cfg.exists():
            content = setup_cfg.read_text(encoding='utf-8')
            if "[tool:pytest]" in content:
                return "pytest"
        
        # Check for test files
        for test_file in repo_path.rglob("test_*.py"):
            return "pytest"
        
        for test_file in repo_path.rglob("*_test.py"):
            return "pytest"
        
        for test_file in repo_path.rglob("*.test.js"):
            return "jest"
        
        for test_file in repo_path.rglob("*.test.ts"):
            return "vitest"
        
        return None
    
    def discover_test_files(self, repo_path: Path, framework: str) -> List[Path]:
        """Discover test files for a framework."""
        test_files = []
        patterns = self.TEST_PATTERNS.get(framework, [])
        
        for pattern in patterns:
            test_files.extend(repo_path.glob(pattern))
            test_files.extend(repo_path.rglob(pattern))
        
        # Remove duplicates
        return list(set(test_files))
    
    def _parse_pytest_output(self, output: str) -> Tuple[int, int, int, int, List[str]]:
        """Parse pytest output for results."""
        passed = failed = skipped = errors = 0
        failed_tests = []
        
        # Match summary line like "5 passed, 2 failed, 1 skipped"
        summary_match = re.search(
            r'(\d+)\s+passed|(\d+)\s+failed|(\d+)\s+skipped|(\d+)\s+error',
            output
        )
        
        # Try full summary pattern
        full_pattern = r'=+\s*(?:(\d+)\s+passed)?[,\s]*(?:(\d+)\s+failed)?[,\s]*(?:(\d+)\s+skipped)?[,\s]*(?:(\d+)\s+error)?'
        full_match = re.search(full_pattern, output)
        
        if full_match:
            passed = int(full_match.group(1) or 0)
            failed = int(full_match.group(2) or 0)
            skipped = int(full_match.group(3) or 0)
            errors = int(full_match.group(4) or 0)
        else:
            # Count individual results
            passed = len(re.findall(r'\s+PASSED', output))
            failed = len(re.findall(r'\s+FAILED', output))
            skipped = len(re.findall(r'\s+SKIPPED', output))
            errors = len(re.findall(r'\s+ERROR', output))
        
        # Extract failed test names
        failed_matches = re.findall(r'FAILED\s+(\S+)', output)
        failed_tests.extend(failed_matches)
        
        return passed, failed, skipped, errors, failed_tests
    
    def _parse_jest_output(self, output: str) -> Tuple[int, int, int, int, List[str]]:
        """Parse Jest/Vitest output for results."""
        passed = failed = skipped = errors = 0
        failed_tests = []
        
        # Jest summary pattern
        tests_pattern = r'Tests:\s+(?:(\d+)\s+failed,?\s*)?(?:(\d+)\s+skipped,?\s*)?(?:(\d+)\s+passed,?\s*)?'
        match = re.search(tests_pattern, output)
        
        if match:
            failed = int(match.group(1) or 0)
            skipped = int(match.group(2) or 0)
            passed = int(match.group(3) or 0)
        else:
            # Check for Vitest format
            passed = len(re.findall(r'✓|✔|PASS', output))
            failed = len(re.findall(r'✕|✖|FAIL', output))
        
        # Extract failed test names
        failed_matches = re.findall(r'FAIL\s+(\S+)', output)
        failed_tests.extend(failed_matches)
        
        return passed, failed, skipped, errors, failed_tests
    
    async def run_tests(
        self, 
        repo_path: Path, 
        framework: str,
        timeout: int = 300,
        use_docker: bool = False
    ) -> TestResult:
        """Run tests for a given framework."""
        start_time = time.time()
        
        command = self.TEST_COMMANDS.get(framework)
        if not command:
            return TestResult(
                framework=framework,
                output=f"Unknown framework: {framework}",
                success=False
            )
        
        try:
            if use_docker:
                # Run in Docker container
                docker_cmd = self._build_docker_command(repo_path, command, framework)
                result = await asyncio.create_subprocess_shell(
                    docker_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=str(repo_path)
                )
            else:
                # Run directly
                # Set up environment
                env = os.environ.copy()
                
                if framework in ["pytest", "unittest"]:
                    # Add repo to PYTHONPATH
                    env["PYTHONPATH"] = str(repo_path)
                
                result = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=str(repo_path),
                    env=env
                )
            
            try:
                stdout, _ = await asyncio.wait_for(
                    result.communicate(), 
                    timeout=timeout
                )
                output = stdout.decode('utf-8', errors='replace')
            except asyncio.TimeoutError:
                result.kill()
                return TestResult(
                    framework=framework,
                    output="Test execution timed out",
                    success=False
                )
            
            duration = time.time() - start_time
            
            # Parse output based on framework
            if framework in ["pytest", "unittest"]:
                passed, failed, skipped, errors, failed_tests = self._parse_pytest_output(output)
            else:
                passed, failed, skipped, errors, failed_tests = self._parse_jest_output(output)
            
            total = passed + failed + skipped + errors
            success = failed == 0 and errors == 0 and total > 0
            
            return TestResult(
                framework=framework,
                passed=passed,
                failed=failed,
                skipped=skipped,
                errors=errors,
                total=total,
                duration_seconds=duration,
                output=output,
                success=success,
                failed_tests=failed_tests
            )
            
        except Exception as e:
            return TestResult(
                framework=framework,
                output=f"Error running tests: {str(e)}",
                success=False
            )
    
    def _build_docker_command(
        self, 
        repo_path: Path, 
        command: str, 
        framework: str
    ) -> str:
        """Build Docker command for running tests."""
        if framework in ["pytest", "unittest"]:
            image = "python:3.11-slim"
            setup = "pip install -r requirements.txt 2>/dev/null || true && "
        else:
            image = "node:18-slim"
            setup = "npm install 2>/dev/null || true && "
        
        return (
            f'docker run --rm '
            f'--network=none '
            f'--memory=512m '
            f'--cpus=1 '
            f'-v "{repo_path}:/app" '
            f'-w /app '
            f'{image} '
            f'/bin/sh -c "{setup}{command}"'
        )
    
    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        Run tests in a repository.
        
        Context should contain:
            - repo_path: Path to the repository
            - framework: (optional) Test framework to use
            - timeout: (optional) Test timeout in seconds
            - use_docker: (optional) Run tests in Docker
        """
        start_time = time.time()
        
        repo_path = context.get("repo_path")
        framework = context.get("framework")
        timeout = context.get("timeout", 300)
        use_docker = context.get("use_docker", False)
        
        if not repo_path:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                error="No repository path provided"
            )
        
        repo_path = Path(repo_path)
        
        if not repo_path.exists():
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                error=f"Repository path does not exist: {repo_path}"
            )
        
        # Detect framework if not provided
        if not framework:
            self.report_progress("detecting", 10, "Detecting test framework")
            framework = self.detect_test_framework(repo_path)
            
            if not framework:
                return AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.FAILED,
                    error="No test framework detected",
                    data={"repo_path": str(repo_path)}
                )
        
        # Discover test files
        self.report_progress("discovering", 20, "Discovering test files")
        test_files = self.discover_test_files(repo_path, framework)
        
        if not test_files:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                error="No test files found",
                data={
                    "framework": framework,
                    "repo_path": str(repo_path)
                }
            )
        
        # Run tests
        self.report_progress("running", 40, f"Running {framework} tests")
        test_result = await self.run_tests(
            repo_path, 
            framework, 
            timeout=timeout,
            use_docker=use_docker
        )
        
        duration = time.time() - start_time
        
        self.report_progress("complete", 100, "Tests completed")
        
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS if test_result.success else AgentStatus.FAILED,
            data={
                "test_result": test_result.to_dict(),
                "framework": framework,
                "test_files_count": len(test_files),
                "all_passed": test_result.success
            },
            duration_seconds=duration
        )
