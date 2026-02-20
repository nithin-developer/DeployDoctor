"""
Sandbox Executor Agent - Runs code in Docker containers for safe execution
Enhanced with comprehensive linting support for Python, JavaScript, TypeScript, and Java
"""
import os
import asyncio
import subprocess
import tempfile
import shutil
import json
import re
from typing import Any, Dict, List, Optional
from agents.base_agent import BaseAgent


class ExecutionResult:
    """Result of code execution"""
    def __init__(self, success: bool, stdout: str, stderr: str, exit_code: int, 
                 error_file: Optional[str] = None, error_line: Optional[int] = None,
                 error_type: Optional[str] = None, error_message: Optional[str] = None):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.error_file = error_file
        self.error_line = error_line
        self.error_type = error_type
        self.error_message = error_message


class SandboxExecutorAgent(BaseAgent):
    """Agent responsible for running code in a sandboxed environment with comprehensive linting"""
    
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
        """Execute code in sandbox and return results with comprehensive linting"""
        repo_path = context.get("repo_path")
        if not repo_path:
            return {"execution_results": [], "error": "No repository path provided"}
        
        # Detect project type
        project_type = self._detect_project_type(repo_path)
        
        # Collect all results
        results = []
        
        # Step 1: Run linting checks FIRST (catches more issues than runtime)
        print(f"  [Sandbox] Running comprehensive linting for {project_type} project...")
        lint_results = await self._run_comprehensive_linting(repo_path, project_type)
        results.extend(lint_results)
        print(f"  [Sandbox] Found {len(lint_results)} linting issues")
        
        # Step 2: Run syntax checks based on project type
        if project_type == "python":
            syntax_results = await self._check_python_syntax(repo_path)
            results.extend(syntax_results)
            print(f"  [Sandbox] Found {len(syntax_results)} Python syntax errors")
        elif project_type in ("node", "typescript"):
            # Run native JSX/TSX syntax checking (works without npm install)
            jsx_results = await self._check_jsx_tsx_syntax(repo_path)
            results.extend(jsx_results)
            print(f"  [Sandbox] Found {len(jsx_results)} JSX/TSX syntax errors")
            
            # Also try TypeScript compiler if available
            ts_results = await self._check_typescript_errors(repo_path)
            results.extend(ts_results)
            print(f"  [Sandbox] Found {len(ts_results)} TypeScript errors")
        elif project_type == "java":
            java_results = await self._check_java_syntax(repo_path)
            results.extend(java_results)
            print(f"  [Sandbox] Found {len(java_results)} Java errors")
        
        # Step 3: Execute project to find runtime errors
        if project_type == "python":
            exec_results = await self._execute_python_project(repo_path)
            results.extend(exec_results)
        elif project_type in ("node", "typescript"):
            exec_results = await self._execute_node_project(repo_path)
            results.extend(exec_results)
        elif project_type == "java":
            exec_results = await self._execute_java_project(repo_path)
            results.extend(exec_results)
        else:
            exec_results = await self._execute_individual_files(repo_path)
            results.extend(exec_results)
        
        # Deduplicate results by file:line:type
        seen = set()
        unique_results = []
        for r in results:
            key = f"{r.error_file}:{r.error_line}:{r.error_type}"
            if key not in seen:
                seen.add(key)
                unique_results.append(r)
        
        return {
            "execution_results": unique_results,
            "project_type": project_type,
            "docker_used": self.docker_available,
            "total_issues": len(unique_results)
        }

    async def _run_comprehensive_linting(self, repo_path: str, project_type: str) -> List[ExecutionResult]:
        """Run comprehensive linting based on project type"""
        results = []
        
        if project_type == "python":
            # Try ruff first (fast, modern linter), fall back to flake8
            ruff_results = await self._run_ruff(repo_path)
            if ruff_results:
                results.extend(ruff_results)
            else:
                # Fallback to flake8
                flake8_results = await self._run_flake8(repo_path)
                results.extend(flake8_results)
            
            # Also run pylint for deeper analysis
            pylint_results = await self._run_pylint(repo_path)
            results.extend(pylint_results)
            
        elif project_type in ("node", "typescript"):
            # Try ESLint for JS/TS (works if node_modules exists)
            eslint_results = await self._run_eslint(repo_path)
            results.extend(eslint_results)
            
            # If no eslint results, use native pattern-based linting
            if not eslint_results:
                native_results = await self._run_native_js_linting(repo_path)
                results.extend(native_results)
        
        elif project_type == "java":
            # Run Java linting
            java_lint_results = await self._run_java_linting(repo_path)
            results.extend(java_lint_results)
        
        return results
    
    async def _run_ruff(self, repo_path: str) -> List[ExecutionResult]:
        """Run ruff linter on Python files"""
        results = []
        try:
            process = await asyncio.create_subprocess_exec(
                'ruff', 'check', '.', '--output-format=json',
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
            
            if stdout:
                try:
                    issues = json.loads(stdout.decode('utf-8', errors='ignore'))
                    for issue in issues:
                        results.append(ExecutionResult(
                            success=False,
                            stdout="",
                            stderr=f"{issue.get('code', 'LINT')}: {issue.get('message', '')}",
                            exit_code=1,
                            error_file=issue.get('filename', '').replace(repo_path + os.sep, ''),
                            error_line=issue.get('location', {}).get('row', 1),
                            error_type="LINTING",
                            error_message=issue.get('message', '')
                        ))
                except json.JSONDecodeError:
                    pass
        except FileNotFoundError:
            print("  [Sandbox] ruff not installed, skipping...")
        except Exception as e:
            print(f"  [Sandbox] ruff error: {e}")
        return results
    
    async def _run_flake8(self, repo_path: str) -> List[ExecutionResult]:
        """Run flake8 linter on Python files"""
        results = []
        try:
            process = await asyncio.create_subprocess_exec(
                'flake8', '--format=json', '.',
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
            
            # Flake8 outputs one JSON object per line
            if stdout:
                for line in stdout.decode('utf-8', errors='ignore').strip().split('\n'):
                    if line:
                        try:
                            issue = json.loads(line)
                            for filename, file_issues in issue.items():
                                for err in file_issues:
                                    results.append(ExecutionResult(
                                        success=False,
                                        stdout="",
                                        stderr=f"{err.get('code', 'E')}: {err.get('text', '')}",
                                        exit_code=1,
                                        error_file=filename.replace(repo_path + os.sep, ''),
                                        error_line=err.get('line_number', 1),
                                        error_type="LINTING",
                                        error_message=err.get('text', '')
                                    ))
                        except json.JSONDecodeError:
                            # Parse non-JSON output format: file.py:line:col: code message
                            match = re.match(r'(.+?):(\d+):(\d+):\s*(\w+)\s+(.+)', line)
                            if match:
                                results.append(ExecutionResult(
                                    success=False,
                                    stdout="",
                                    stderr=f"{match.group(4)}: {match.group(5)}",
                                    exit_code=1,
                                    error_file=match.group(1).replace(repo_path + os.sep, ''),
                                    error_line=int(match.group(2)),
                                    error_type="LINTING",
                                    error_message=match.group(5)
                                ))
        except FileNotFoundError:
            print("  [Sandbox] flake8 not installed, skipping...")
        except Exception as e:
            print(f"  [Sandbox] flake8 error: {e}")
        return results
    
    async def _run_pylint(self, repo_path: str) -> List[ExecutionResult]:
        """Run pylint for deeper Python analysis"""
        results = []
        try:
            # Find all Python files
            py_files = []
            for root, dirs, files in os.walk(repo_path):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in 
                          ['node_modules', '__pycache__', 'venv', '.venv', 'dist', 'build']]
                for f in files:
                    if f.endswith('.py'):
                        rel_path = os.path.relpath(os.path.join(root, f), repo_path)
                        py_files.append(rel_path)
            
            if not py_files:
                return results
            
            process = await asyncio.create_subprocess_exec(
                'pylint', '--output-format=json', '--disable=C,R',  # Only errors and warnings
                *py_files[:20],  # Limit number of files
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
            
            if stdout:
                try:
                    issues = json.loads(stdout.decode('utf-8', errors='ignore'))
                    for issue in issues:
                        # Only include errors and warnings (not conventions/refactors)
                        if issue.get('type') in ('error', 'warning'):
                            results.append(ExecutionResult(
                                success=False,
                                stdout="",
                                stderr=f"{issue.get('symbol', 'E')}: {issue.get('message', '')}",
                                exit_code=1,
                                error_file=issue.get('path', ''),
                                error_line=issue.get('line', 1),
                                error_type=issue.get('symbol', 'LINTING').upper(),
                                error_message=issue.get('message', '')
                            ))
                except json.JSONDecodeError:
                    pass
        except FileNotFoundError:
            print("  [Sandbox] pylint not installed, skipping...")
        except Exception as e:
            print(f"  [Sandbox] pylint error: {e}")
        return results
    
    async def _run_eslint(self, repo_path: str) -> List[ExecutionResult]:
        """Run ESLint on JavaScript/TypeScript files"""
        results = []
        try:
            # Check if eslint is available (local or global)
            eslint_cmd = 'eslint'
            local_eslint = os.path.join(repo_path, 'node_modules', '.bin', 'eslint')
            if os.path.exists(local_eslint):
                eslint_cmd = local_eslint
            
            process = await asyncio.create_subprocess_exec(
                eslint_cmd, '.', '--format=json', '--ext', '.js,.jsx,.ts,.tsx',
                '--no-error-on-unmatched-pattern',
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
            
            if stdout:
                try:
                    files = json.loads(stdout.decode('utf-8', errors='ignore'))
                    for file_result in files:
                        filepath = file_result.get('filePath', '').replace(repo_path + os.sep, '')
                        for msg in file_result.get('messages', []):
                            severity = 'error' if msg.get('severity', 0) == 2 else 'warning'
                            results.append(ExecutionResult(
                                success=False,
                                stdout="",
                                stderr=f"{msg.get('ruleId', 'eslint')}: {msg.get('message', '')}",
                                exit_code=1,
                                error_file=filepath,
                                error_line=msg.get('line', 1),
                                error_type="LINTING",
                                error_message=msg.get('message', '')
                            ))
                except json.JSONDecodeError:
                    pass
        except FileNotFoundError:
            print("  [Sandbox] eslint not installed, skipping...")
        except Exception as e:
            print(f"  [Sandbox] eslint error: {e}")
        return results
    
    async def _check_typescript_errors(self, repo_path: str) -> List[ExecutionResult]:
        """Run TypeScript compiler to check for type errors"""
        results = []
        
        # Check if tsconfig.json exists
        tsconfig_path = os.path.join(repo_path, 'tsconfig.json')
        if not os.path.exists(tsconfig_path):
            return results
        
        try:
            # Check for local tsc
            tsc_cmd = 'tsc'
            local_tsc = os.path.join(repo_path, 'node_modules', '.bin', 'tsc')
            if os.path.exists(local_tsc):
                tsc_cmd = local_tsc
            
            process = await asyncio.create_subprocess_exec(
                tsc_cmd, '--noEmit', '--pretty', 'false',
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
            
            output = stdout.decode('utf-8', errors='ignore') + stderr.decode('utf-8', errors='ignore')
            
            # Parse tsc output: file(line,col): error TSxxxx: message
            for line in output.strip().split('\n'):
                match = re.match(r'(.+?)\((\d+),(\d+)\):\s*(error|warning)\s+(TS\d+):\s*(.+)', line)
                if match:
                    results.append(ExecutionResult(
                        success=False,
                        stdout="",
                        stderr=f"{match.group(5)}: {match.group(6)}",
                        exit_code=1,
                        error_file=match.group(1).replace(repo_path + os.sep, ''),
                        error_line=int(match.group(2)),
                        error_type="TYPE_ERROR",
                        error_message=match.group(6)
                    ))
        except FileNotFoundError:
            print("  [Sandbox] tsc not installed, skipping...")
        except Exception as e:
            print(f"  [Sandbox] tsc error: {e}")
        
        return results
    
    async def _check_jsx_tsx_syntax(self, repo_path: str) -> List[ExecutionResult]:
        """Native JSX/TSX/JS/TS syntax checking without requiring npm install.
        Uses pattern-based detection for common syntax errors.
        """
        results = []
        
        # File extensions to check
        extensions = ('.js', '.jsx', '.ts', '.tsx')
        
        for root, dirs, files in os.walk(repo_path):
            # Skip node_modules, dist, build, etc.
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in 
                      ['node_modules', '__pycache__', 'venv', '.venv', 'dist', 'build', '.git']]
            
            for file in files:
                if file.endswith(extensions):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, repo_path)
                    
                    file_errors = await self._check_single_jsx_file(file_path, relative_path)
                    results.extend(file_errors)
        
        return results
    
    async def _check_single_jsx_file(self, file_path: str, relative_path: str) -> List[ExecutionResult]:
        """Check a single JSX/TSX/JS/TS file for syntax errors.
        Uses conservative approach - only reports clear syntax errors to minimize false positives.
        """
        results = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            return [ExecutionResult(
                success=False, stdout="", stderr=f"Error reading file: {e}",
                exit_code=1, error_file=relative_path, error_type="FILE_READ_ERROR"
            )]
        
        # Simplified bracket tracking - only for significant imbalances
        bracket_counts = {'(': 0, '{': 0, '[': 0}
        in_string = False
        string_char = None
        in_template = False
        in_multiline_comment = False
        
        for line_num, line in enumerate(lines, 1):
            i = 0
            while i < len(line):
                # Handle multiline comments
                if in_multiline_comment:
                    if i < len(line) - 1 and line[i:i+2] == '*/':
                        in_multiline_comment = False
                        i += 2
                        continue
                    i += 1
                    continue
                
                # Check for start of multiline comment
                if not in_string and not in_template and i < len(line) - 1 and line[i:i+2] == '/*':
                    in_multiline_comment = True
                    i += 2
                    continue
                
                # Skip single-line comments
                if not in_string and not in_template and i < len(line) - 1 and line[i:i+2] == '//':
                    break
                
                char = line[i]
                
                # Handle template literals - skip everything inside them
                if char == '`' and not in_string:
                    in_template = not in_template
                    i += 1
                    continue
                
                # Skip template literal content entirely (may contain embedded syntax)
                if in_template:
                    i += 1
                    continue
                
                # Handle strings
                if in_string:
                    if char == '\\' and i + 1 < len(line):
                        i += 2  # Skip escaped character
                        continue
                    if char == string_char:
                        in_string = False
                        string_char = None
                    i += 1
                    continue
                
                # Start of string
                if char in '"\'':
                    in_string = True
                    string_char = char
                    i += 1
                    continue
                
                # Track brackets only when not in string/template
                if char in '({[':
                    bracket_counts[char] += 1
                elif char == ')':
                    bracket_counts['('] -= 1
                elif char == '}':
                    bracket_counts['{'] -= 1
                elif char == ']':
                    bracket_counts['['] -= 1
                
                i += 1
        
        # Only report if there's a significant bracket imbalance at EOF
        # This indicates the file is genuinely broken
        expected_closers = {'(': ')', '{': '}', '[': ']'}
        for bracket, count in bracket_counts.items():
            if count > 2:  # Only report if multiple unclosed (likely real error)
                results.append(ExecutionResult(
                    success=False, stdout="",
                    stderr=f"File may have unclosed '{bracket}' brackets (found {count} extra)",
                    exit_code=1, error_file=relative_path, error_line=1,
                    error_type="SYNTAX_ERROR", error_message=f"Potential unclosed '{bracket}' brackets"
                ))
            elif count < -2:  # Only report if multiple extra closing (likely real error)
                results.append(ExecutionResult(
                    success=False, stdout="",
                    stderr=f"File may have extra '{expected_closers[bracket]}' brackets (found {-count} extra)",
                    exit_code=1, error_file=relative_path, error_line=1,
                    error_type="SYNTAX_ERROR", error_message=f"Potential extra '{expected_closers[bracket]}' brackets"
                ))
        
        # Additional pattern-based checks (only real errors, not style)
        pattern_errors = self._check_js_patterns(content, lines, relative_path)
        results.extend(pattern_errors)
        
        return results
    
    def _check_js_patterns(self, content: str, lines: List[str], relative_path: str) -> List[ExecutionResult]:
        """Check for common JavaScript/TypeScript error patterns - only real errors, not style"""
        results = []
        
        patterns = [
            # Debugger statements - should be removed
            (r'\bdebugger\b', 'DEBUGGER', 'Debugger statement found (remove before production)'),
            # Empty catch blocks - potential error hiding
            (r'catch\s*\([^)]*\)\s*\{\s*\}', 'EMPTY_CATCH', 'Empty catch block (may hide errors)'),
            # Assignment in condition
            (r'\bif\s*\(\s*\w+\s*=\s*[^=]', 'ASSIGNMENT_IN_CONDITION', 'Assignment in condition (use === for comparison)'),
            # != instead of !==
            (r'[^!]!=[^=]', 'LOOSE_INEQUALITY', 'Use !== instead of !='),
        ]
        
        for line_num, line in enumerate(lines, 1):
            # Skip comments
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                continue
            
            for pattern, error_type, message in patterns:
                if re.search(pattern, line):
                    # Only report actual errors, not style suggestions
                    if error_type in ('DEBUGGER', 'EMPTY_CATCH', 'ASSIGNMENT_IN_CONDITION'):
                        results.append(ExecutionResult(
                            success=False, stdout="", stderr=message,
                            exit_code=1, error_file=relative_path, error_line=line_num,
                            error_type=error_type, error_message=message
                        ))
        
        # Check for specific React issues
        if '.tsx' in relative_path or '.jsx' in relative_path:
            react_errors = self._check_react_patterns(lines, relative_path)
            results.extend(react_errors)
        
        return results
    
    def _check_react_patterns(self, lines: List[str], relative_path: str) -> List[ExecutionResult]:
        """Check for common React-specific errors"""
        results = []
        
        for line_num, line in enumerate(lines, 1):
            # Check for invalid JSX attributes
            # class instead of className
            if re.search(r'<\w+[^>]*\bclass\s*=', line) and 'className' not in line:
                results.append(ExecutionResult(
                    success=False, stdout="",
                    stderr="Use 'className' instead of 'class' in JSX",
                    exit_code=1, error_file=relative_path, error_line=line_num,
                    error_type="JSX_ERROR", error_message="Use 'className' instead of 'class'"
                ))
            
            # for instead of htmlFor
            if re.search(r'<label[^>]*\bfor\s*=', line) and 'htmlFor' not in line:
                results.append(ExecutionResult(
                    success=False, stdout="",
                    stderr="Use 'htmlFor' instead of 'for' in JSX label",
                    exit_code=1, error_file=relative_path, error_line=line_num,
                    error_type="JSX_ERROR", error_message="Use 'htmlFor' instead of 'for'"
                ))
            
            # Missing key in map
            if '.map(' in line and 'key=' not in line and 'key:' not in line:
                # Check next few lines for key
                has_key = False
                for check_line in lines[line_num-1:line_num+3]:
                    if 'key=' in check_line or 'key:' in check_line:
                        has_key = True
                        break
                if not has_key and ('<' in line or 'return' in line):
                    results.append(ExecutionResult(
                        success=False, stdout="",
                        stderr="Missing 'key' prop in list rendering",
                        exit_code=1, error_file=relative_path, error_line=line_num,
                        error_type="REACT_WARNING", error_message="Missing 'key' prop in list"
                    ))
        
        return results
    
    async def _run_native_js_linting(self, repo_path: str) -> List[ExecutionResult]:
        """Native JS/TS linting without ESLint for when node_modules isn't available"""
        # This is covered by _check_jsx_tsx_syntax and _check_js_patterns
        # This method can be expanded with more checks
        return []
    
    async def _check_java_syntax(self, repo_path: str) -> List[ExecutionResult]:
        """Check Java files for syntax errors using javac"""
        results = []
        
        # Find all Java files
        java_files = []
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in 
                      ['target', 'build', 'out', '.gradle', '.idea']]
            for file in files:
                if file.endswith('.java'):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, repo_path)
                    java_files.append(rel_path)
        
        if not java_files:
            return results
        
        try:
            # Use javac to check syntax (compile without running)
            process = await asyncio.create_subprocess_exec(
                'javac', '-d', tempfile.gettempdir(), '-Xlint:all',
                *java_files[:50],  # Limit number of files
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
            
            error_output = stderr.decode('utf-8', errors='ignore')
            
            # Parse javac output: filename.java:line: error: message
            for line in error_output.strip().split('\n'):
                match = re.match(r'(.+\.java):(\d+):\s*(error|warning):\s*(.+)', line)
                if match:
                    results.append(ExecutionResult(
                        success=False, stdout="",
                        stderr=f"{match.group(3)}: {match.group(4)}",
                        exit_code=1,
                        error_file=match.group(1),
                        error_line=int(match.group(2)),
                        error_type="JAVA_ERROR" if match.group(3) == 'error' else "JAVA_WARNING",
                        error_message=match.group(4)
                    ))
        except FileNotFoundError:
            print("  [Sandbox] javac not installed, skipping Java syntax check...")
        except Exception as e:
            print(f"  [Sandbox] javac error: {e}")
        
        return results
    
    async def _run_java_linting(self, repo_path: str) -> List[ExecutionResult]:
        """Run Java linting (uses javac warnings)"""
        # Java linting is handled by _check_java_syntax with -Xlint:all flag
        return []
    
    async def _execute_java_project(self, repo_path: str) -> List[ExecutionResult]:
        """Execute Java project to find runtime errors"""
        results = []
        
        # Check for Maven project
        if os.path.exists(os.path.join(repo_path, 'pom.xml')):
            try:
                process = await asyncio.create_subprocess_exec(
                    'mvn', 'compile', '-q',
                    cwd=repo_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
                
                if process.returncode != 0:
                    error_output = stderr.decode('utf-8', errors='ignore')
                    for line in error_output.split('\n'):
                        if '[ERROR]' in line:
                            results.append(ExecutionResult(
                                success=False, stdout="",
                                stderr=line,
                                exit_code=1,
                                error_type="MAVEN_ERROR",
                                error_message=line
                            ))
            except FileNotFoundError:
                print("  [Sandbox] Maven not installed, skipping...")
            except Exception as e:
                print(f"  [Sandbox] Maven error: {e}")
        
        # Check for Gradle project
        elif os.path.exists(os.path.join(repo_path, 'build.gradle')) or \
             os.path.exists(os.path.join(repo_path, 'build.gradle.kts')):
            try:
                gradle_cmd = './gradlew' if os.path.exists(os.path.join(repo_path, 'gradlew')) else 'gradle'
                process = await asyncio.create_subprocess_exec(
                    gradle_cmd, 'compileJava', '-q',
                    cwd=repo_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
                
                if process.returncode != 0:
                    error_output = stderr.decode('utf-8', errors='ignore')
                    results.append(ExecutionResult(
                        success=False, stdout="",
                        stderr=error_output[:500],
                        exit_code=1,
                        error_type="GRADLE_ERROR",
                        error_message="Gradle compilation failed"
                    ))
            except FileNotFoundError:
                print("  [Sandbox] Gradle not installed, skipping...")
            except Exception as e:
                print(f"  [Sandbox] Gradle error: {e}")
        
        return results
    
    def _detect_project_type(self, repo_path: str) -> str:
        """Detect the type of project"""
        # Check for Python project indicators
        if os.path.exists(os.path.join(repo_path, 'requirements.txt')) or \
           os.path.exists(os.path.join(repo_path, 'setup.py')) or \
           os.path.exists(os.path.join(repo_path, 'pyproject.toml')):
            return "python"
        
        # Check for Java project indicators
        if os.path.exists(os.path.join(repo_path, 'pom.xml')) or \
           os.path.exists(os.path.join(repo_path, 'build.gradle')) or \
           os.path.exists(os.path.join(repo_path, 'build.gradle.kts')):
            return "java"
        
        # Check for TypeScript project (tsconfig.json)
        if os.path.exists(os.path.join(repo_path, 'tsconfig.json')):
            return "typescript"
        
        # Check for Node.js project
        if os.path.exists(os.path.join(repo_path, 'package.json')):
            return "node"
        
        # Check for main files
        for f in os.listdir(repo_path):
            if f.endswith('.py'):
                return "python"
            if f.endswith('.java'):
                return "java"
            if f.endswith('.ts') or f.endswith('.tsx'):
                return "typescript"
            if f.endswith(('.js', '.jsx')):
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
