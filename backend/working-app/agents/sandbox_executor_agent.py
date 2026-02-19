"""
Sandbox Executor Agent - Runs code in Docker containers for safe execution
"""
import os
import asyncio
import subprocess
import tempfile
import shutil
from typing import Any, Dict, List, Optional
from agents.base_agent import BaseAgent


class ExecutionResult:
    """Result of code execution"""
    def __init__(self, success: bool, stdout: str, stderr: str, exit_code: int, 
                 error_file: Optional[str] = None, error_line: Optional[int] = None,
                 error_type: Optional[str] = None):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.error_file = error_file
        self.error_line = error_line
        self.error_type = error_type


class SandboxExecutorAgent(BaseAgent):
    """Agent responsible for running code in a sandboxed environment"""
    
    def __init__(self):
        super().__init__(
            name="Sandbox Executor Agent",
            description="I run code in isolated environments (Docker or subprocess) to detect runtime errors safely."
        )
        self.docker_available = self._check_docker()
    
    def _check_docker(self) -> bool:
        """Check if Docker is available"""
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
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute code in sandbox and return results"""
        repo_path = context.get("repo_path")
        if not repo_path:
            return {"execution_results": [], "error": "No repository path provided"}
        
        # Detect project type
        project_type = self._detect_project_type(repo_path)
        
        # Execute based on project type
        results = []
        
        if project_type == "python":
            results = await self._execute_python_project(repo_path)
        elif project_type == "node":
            results = await self._execute_node_project(repo_path)
        else:
            # Try to run individual files
            results = await self._execute_individual_files(repo_path)
        
        return {
            "execution_results": results,
            "project_type": project_type,
            "docker_used": self.docker_available
        }
    
    def _detect_project_type(self, repo_path: str) -> str:
        """Detect the type of project"""
        if os.path.exists(os.path.join(repo_path, 'requirements.txt')) or \
           os.path.exists(os.path.join(repo_path, 'setup.py')) or \
           os.path.exists(os.path.join(repo_path, 'pyproject.toml')):
            return "python"
        
        if os.path.exists(os.path.join(repo_path, 'package.json')):
            return "node"
        
        # Check for main files
        for f in os.listdir(repo_path):
            if f.endswith('.py'):
                return "python"
            if f.endswith(('.js', '.ts')):
                return "node"
        
        return "unknown"
    
    async def _execute_python_project(self, repo_path: str) -> List[ExecutionResult]:
        """Execute a Python project"""
        results = []
        
        # Find entry points
        entry_points = self._find_python_entry_points(repo_path)
        
        for entry_point in entry_points:
            if self.docker_available:
                result = await self._run_in_docker_python(repo_path, entry_point)
            else:
                result = await self._run_python_subprocess(repo_path, entry_point)
            results.append(result)
        
        # Also run syntax check on all Python files
        syntax_results = await self._check_python_syntax(repo_path)
        results.extend(syntax_results)
        
        return results
    
    def _find_python_entry_points(self, repo_path: str) -> List[str]:
        """Find Python entry point files"""
        entry_points = []
        
        # Common entry point names
        common_names = ['main.py', 'app.py', 'run.py', '__main__.py', 'server.py', 'index.py']
        
        for name in common_names:
            path = os.path.join(repo_path, name)
            if os.path.exists(path):
                entry_points.append(name)
        
        # If no common entry points, try all Python files in root
        if not entry_points:
            for f in os.listdir(repo_path):
                if f.endswith('.py') and not f.startswith('test_') and not f.startswith('_'):
                    entry_points.append(f)
        
        return entry_points[:3]  # Limit to first 3
    
    async def _run_in_docker_python(self, repo_path: str, entry_point: str) -> ExecutionResult:
        """Run Python code in Docker container"""
        try:
            # Create a simple Dockerfile
            dockerfile_content = """FROM python:3.11-slim
WORKDIR /app
COPY . /app/
RUN pip install --no-cache-dir -r requirements.txt 2>/dev/null || true
CMD ["python", "{entry_point}"]
""".format(entry_point=entry_point)
            
            temp_dockerfile = os.path.join(repo_path, 'Dockerfile.temp')
            with open(temp_dockerfile, 'w') as f:
                f.write(dockerfile_content)
            
            # Build and run container with timeout
            container_name = f"ai_analyzer_{os.getpid()}"
            
            # Build image
            build_cmd = ['docker', 'build', '-f', 'Dockerfile.temp', '-t', container_name, '.']
            build_process = await asyncio.create_subprocess_exec(
                *build_cmd,
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(build_process.communicate(), timeout=120)
            
            # Run container
            run_cmd = ['docker', 'run', '--rm', '--network=none', 
                      '--memory=256m', '--cpus=0.5', container_name]
            run_process = await asyncio.create_subprocess_exec(
                *run_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(run_process.communicate(), timeout=30)
                stdout_str = stdout.decode('utf-8', errors='ignore')
                stderr_str = stderr.decode('utf-8', errors='ignore')
                
                result = self._parse_python_error(stderr_str, entry_point)
                result.stdout = stdout_str
                return result
                
            except asyncio.TimeoutError:
                run_process.kill()
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr="Execution timed out after 30 seconds",
                    exit_code=-1,
                    error_type="TIMEOUT"
                )
            finally:
                # Cleanup
                os.remove(temp_dockerfile) if os.path.exists(temp_dockerfile) else None
                subprocess.run(['docker', 'rmi', '-f', container_name], 
                             capture_output=True, timeout=10)
                
        except Exception as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                error_type="DOCKER_ERROR"
            )
    
    async def _run_python_subprocess(self, repo_path: str, entry_point: str) -> ExecutionResult:
        """Run Python code in subprocess (fallback when Docker not available)"""
        try:
            file_path = os.path.join(repo_path, entry_point)
            
            process = await asyncio.create_subprocess_exec(
                'python', '-c', f'''
import sys
sys.path.insert(0, r"{repo_path}")
try:
    exec(open(r"{file_path}", encoding="utf-8").read())
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
''',
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
                stdout_str = stdout.decode('utf-8', errors='ignore')
                stderr_str = stderr.decode('utf-8', errors='ignore')
                
                return self._parse_python_error(stderr_str, entry_point)
                
            except asyncio.TimeoutError:
                process.kill()
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
                error_type="EXECUTION_ERROR"
            )
    
    async def _check_python_syntax(self, repo_path: str) -> List[ExecutionResult]:
        """Check syntax of all Python files using ast.parse.
        Uses iterative approach to find multiple syntax errors in a single file.
        """
        import ast
        results = []
        
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in 
                      ['node_modules', '__pycache__', 'venv', '.venv', 'dist', 'build']]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, repo_path)
                    
                    # Find ALL syntax errors in this file
                    file_errors = await self._find_all_syntax_errors(file_path, relative_path)
                    results.extend(file_errors)
        
        return results
    
    async def _find_all_syntax_errors(self, file_path: str, relative_path: str) -> List[ExecutionResult]:
        """Find all syntax errors in a Python file using iterative parsing.
        After finding an error, tries to locate additional errors by parsing remaining code.
        """
        import ast
        results = []
        found_error_lines = set()
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception as e:
            return [ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Error reading {relative_path}: {str(e)}",
                exit_code=-1,
                error_file=relative_path,
                error_type="FILE_READ_ERROR"
            )]
        
        # First pass: find the first syntax error normally
        source_code = ''.join(lines)
        
        try:
            ast.parse(source_code, filename=file_path)
            return []  # No syntax errors
        except SyntaxError as e:
            if e.lineno:
                found_error_lines.add(e.lineno)
                results.append(self._create_syntax_error_result(e, relative_path))
        except Exception:
            pass
        
        # Second pass: try to find additional errors by commenting out error lines
        # and parsing remaining code
        max_iterations = 10  # Limit to prevent infinite loops
        iteration = 0
        
        while iteration < max_iterations and results:
            iteration += 1
            # Comment out known error lines
            modified_lines = []
            for i, line in enumerate(lines, 1):
                if i in found_error_lines:
                    # Replace with pass to maintain line numbers
                    indent = len(line) - len(line.lstrip())
                    modified_lines.append(' ' * indent + 'pass  # [SYNTAX_CHECK_PLACEHOLDER]\n')
                else:
                    modified_lines.append(line)
            
            modified_source = ''.join(modified_lines)
            
            try:
                ast.parse(modified_source, filename=file_path)
                break  # No more errors
            except SyntaxError as e:
                if e.lineno and e.lineno not in found_error_lines:
                    found_error_lines.add(e.lineno)
                    # Read original line for error context
                    original_error = SyntaxError(e.msg)
                    original_error.lineno = e.lineno
                    original_error.offset = e.offset
                    original_error.text = lines[e.lineno - 1] if e.lineno <= len(lines) else None
                    original_error.msg = e.msg
                    results.append(self._create_syntax_error_result(original_error, relative_path))
                else:
                    break  # Same error or no line number
            except Exception:
                break
        
        return results
    
    def _create_syntax_error_result(self, e: SyntaxError, relative_path: str) -> ExecutionResult:
        """Create an ExecutionResult from a SyntaxError"""
        error_msg = f"SyntaxError: {e.msg}\nFile: {relative_path}, Line: {e.lineno}\n"
        if e.text:
            error_msg += f"    {e.text.rstrip()}\n"
            if e.offset:
                error_msg += f"    {' ' * (e.offset - 1)}^\n"
        
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=error_msg,
            exit_code=1,
            error_file=relative_path,
            error_line=e.lineno,
            error_type="SyntaxError"
        )
        
        return results
    
    def _parse_python_error(self, stderr: str, file_hint: str) -> ExecutionResult:
        """Parse Python error output to extract error details"""
        import re
        
        if not stderr.strip():
            return ExecutionResult(
                success=True,
                stdout="",
                stderr="",
                exit_code=0
            )
        
        # Parse traceback for file and line info
        # Pattern: File "path", line X
        file_match = re.search(r'File ["\']([^"\']+)["\'], line (\d+)', stderr)
        error_file = file_match.group(1) if file_match else file_hint
        error_line = int(file_match.group(2)) if file_match else None
        
        # Get error type (e.g., SyntaxError, NameError, etc.)
        error_type_match = re.search(r'(\w+Error|\w+Exception):', stderr)
        error_type = error_type_match.group(1) if error_type_match else "RuntimeError"
        
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=stderr,
            exit_code=1,
            error_file=error_file,
            error_line=error_line,
            error_type=error_type
        )
    
    async def _execute_node_project(self, repo_path: str) -> List[ExecutionResult]:
        """Execute a Node.js project"""
        results = []
        
        # Check package.json for scripts
        package_json_path = os.path.join(repo_path, 'package.json')
        if os.path.exists(package_json_path):
            import json
            try:
                with open(package_json_path) as f:
                    pkg = json.load(f)
                
                main_file = pkg.get('main', 'index.js')
                if os.path.exists(os.path.join(repo_path, main_file)):
                    result = await self._run_node_file(repo_path, main_file)
                    results.append(result)
            except Exception as e:
                results.append(ExecutionResult(
                    success=False,
                    stdout="",
                    stderr=str(e),
                    exit_code=-1,
                    error_type="NODE_ERROR"
                ))
        
        return results
    
    async def _run_node_file(self, repo_path: str, entry_point: str) -> ExecutionResult:
        """Run a Node.js file"""
        try:
            process = await asyncio.create_subprocess_exec(
                'node', '--check', entry_point,
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            stdout_str = stdout.decode('utf-8', errors='ignore')
            stderr_str = stderr.decode('utf-8', errors='ignore')
            
            return ExecutionResult(
                success=process.returncode == 0,
                stdout=stdout_str,
                stderr=stderr_str,
                exit_code=process.returncode,
                error_file=entry_point if process.returncode != 0 else None,
                error_type="SyntaxError" if process.returncode != 0 else None
            )
            
        except Exception as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                error_type="NODE_ERROR"
            )
    
    async def _execute_individual_files(self, repo_path: str) -> List[ExecutionResult]:
        """Execute individual files when project type is unknown"""
        results = []
        
        # Check Python files
        for f in os.listdir(repo_path):
            if f.endswith('.py') and os.path.isfile(os.path.join(repo_path, f)):
                result = await self._run_python_subprocess(repo_path, f)
                if not result.success:
                    results.append(result)
        
        return results
