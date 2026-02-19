"""
Test Runner Agent - Discovers and runs tests in the repository
"""
import os
import subprocess
import asyncio
from typing import Any, Dict, List
from langchain_core.messages import SystemMessage, HumanMessage
from agents.base_agent import BaseAgent
from models import TestResult


class TestRunnerAgent(BaseAgent):
    """Agent responsible for discovering and running tests in the repository"""
    
    def __init__(self):
        super().__init__(
            name="Test Runner Agent",
            description="I discover and run tests in repositories. I support Python (pytest, unittest), JavaScript/TypeScript (jest, mocha, vitest), and other common test frameworks."
        )
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute test discovery and running"""
        repo_path = context.get("repo_path")
        if not repo_path:
            return {"test_results": [], "error": "No repository path provided"}
        
        # Detect test framework
        framework = await self._detect_test_framework(repo_path)
        
        if not framework:
            return {
                "test_results": [],
                "framework_detected": None,
                "message": "No test framework detected"
            }
        
        # Run tests
        test_results = await self._run_tests(repo_path, framework)
        
        return {
            "test_results": test_results,
            "framework_detected": framework,
            "total_tests": len(test_results),
            "passed": sum(1 for t in test_results if t.passed),
            "failed": sum(1 for t in test_results if not t.passed)
        }
    
    async def _detect_test_framework(self, repo_path: str) -> str:
        """Detect what test framework is used in the repository"""
        
        # Check for Python test frameworks
        requirements_files = ['requirements.txt', 'requirements-dev.txt', 'setup.py', 'pyproject.toml']
        for req_file in requirements_files:
            req_path = os.path.join(repo_path, req_file)
            if os.path.exists(req_path):
                try:
                    with open(req_path, 'r', encoding='utf-8') as f:
                        content = f.read().lower()
                        if 'pytest' in content:
                            return 'pytest'
                        if 'unittest' in content:
                            return 'unittest'
                except:
                    pass
        
        # Check for JavaScript/TypeScript test frameworks
        package_json_path = os.path.join(repo_path, 'package.json')
        if os.path.exists(package_json_path):
            try:
                import json
                with open(package_json_path, 'r', encoding='utf-8') as f:
                    pkg = json.load(f)
                    deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}
                    
                    if 'vitest' in deps:
                        return 'vitest'
                    if 'jest' in deps:
                        return 'jest'
                    if 'mocha' in deps:
                        return 'mocha'
                    
                    # Check scripts for test command
                    scripts = pkg.get('scripts', {})
                    test_script = scripts.get('test', '')
                    if 'vitest' in test_script:
                        return 'vitest'
                    if 'jest' in test_script:
                        return 'jest'
                    if 'mocha' in test_script:
                        return 'mocha'
            except:
                pass
        
        # Check for test directories
        test_dirs = ['tests', 'test', '__tests__', 'spec']
        for test_dir in test_dirs:
            test_path = os.path.join(repo_path, test_dir)
            if os.path.isdir(test_path):
                # Check file extensions to guess framework
                for f in os.listdir(test_path):
                    if f.endswith('.py'):
                        return 'pytest'
                    if f.endswith(('.js', '.ts', '.jsx', '.tsx')):
                        return 'jest'
        
        # Look for test files directly
        for f in os.listdir(repo_path):
            if f.startswith('test_') and f.endswith('.py'):
                return 'pytest'
            if f.endswith('.test.js') or f.endswith('.test.ts'):
                return 'jest'
        
        return None
    
    async def _run_tests(self, repo_path: str, framework: str) -> List[TestResult]:
        """Run tests using the detected framework"""
        results = []
        
        try:
            if framework == 'pytest':
                results = await self._run_pytest(repo_path)
            elif framework == 'unittest':
                results = await self._run_unittest(repo_path)
            elif framework in ['jest', 'vitest', 'mocha']:
                results = await self._run_npm_tests(repo_path, framework)
            else:
                results = [TestResult(
                    test_name="framework_detection",
                    passed=False,
                    error_message=f"Unsupported framework: {framework}"
                )]
        except Exception as e:
            results = [TestResult(
                test_name="test_execution",
                passed=False,
                error_message=str(e)
            )]
        
        return results
    
    async def _run_pytest(self, repo_path: str) -> List[TestResult]:
        """Run pytest tests with detailed failure capture"""
        results = []
        
        try:
            # Use synchronous subprocess.run() instead of asyncio - more reliable on Windows
            import subprocess as sync_subprocess
            
            process = sync_subprocess.run(
                ['python', '-m', 'pytest', '-v', '--tb=long', '-rA'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            output = process.stdout or ""
            stderr_output = process.stderr or ""
            full_output = output + "\n" + stderr_output
            
            # DEBUG: Log the actual pytest output
            print(f"  [TestRunner] pytest stdout length: {len(output)}")
            print(f"  [TestRunner] pytest stderr length: {len(stderr_output)}")
            print(f"  [TestRunner] pytest exit code: {process.returncode}")
            if full_output:
                print(f"  [TestRunner] pytest output preview: {full_output[:500]}...")
            
            # Parse pytest output with detailed failure info
            results = self._parse_pytest_detailed_output(full_output, repo_path)
            print(f"  [TestRunner] _parse_pytest_detailed_output returned {len(results)} results")
            
            # If no results parsed, try verbose parsing
            if not results:
                results = self._parse_pytest_verbose_output(full_output)
                print(f"  [TestRunner] _parse_pytest_verbose_output returned {len(results)} results")
            
            # If still no results but there was output, check for pytest crash/import errors
            if not results and (output or stderr_output):
                crash_result = self._parse_pytest_crash(full_output, repo_path)
                if crash_result:
                    results = [crash_result]
                    print(f"  [TestRunner] _parse_pytest_crash found: {crash_result.test_name}")
                    
            # Fallback: If still no results but pytest ran with output, create a generic failure
            if not results and full_output.strip():
                # Check if there were actually failures
                if 'FAILED' in full_output or 'ERROR' in full_output or 'failed' in full_output.lower():
                    results = [TestResult(
                        test_name="pytest_parse_error",
                        passed=False,
                        error_message=f"Test failures detected but couldn't parse output. Raw output: {full_output[:1000]}",
                        file_path=None,
                        line_number=None,
                        failure_type="UNKNOWN"
                    )]
                    print(f"  [TestRunner] Fallback: created generic test failure result")
                    
        except sync_subprocess.TimeoutExpired:
            results = [TestResult(
                test_name="pytest_timeout",
                passed=False,
                error_message="Test execution timed out after 5 minutes"
            )]
        except Exception as e:
            error_msg = str(e) if str(e) else f"Unknown error: {type(e).__name__}"
            print(f"  [TestRunner] Exception during pytest: {error_msg}")
            results = [TestResult(
                test_name="pytest_error",
                passed=False,
                error_message=error_msg
            )]
        
        return results
    
    def _parse_pytest_crash(self, output: str, repo_path: str) -> TestResult:
        """Parse pytest crash output to extract import errors, etc."""
        import re
        
        print(f"  [TestRunner] _parse_pytest_crash analyzing output len={len(output)}")
        
        # Look for ImportError or ModuleNotFoundError
        import_error = re.search(
            r'(ImportError|ModuleNotFoundError):\s*(.*?)(?:\n|$)',
            output
        )
        if import_error:
            error_type = import_error.group(1)
            error_msg = import_error.group(2).strip()
            
            print(f"  [TestRunner] Found import error: {error_type}: {error_msg}")
            
            # Try to find which file caused the import error
            file_pattern = r'([a-zA-Z_][\w]*\.py)[\'"]?\s*,\s*line\s*(\d+)'
            file_match = re.search(file_pattern, output)
            
            if file_match:
                source_file = file_match.group(1)
                line_num = int(file_match.group(2))
            else:
                # Try to find file from "collecting ... <test_file.py>"
                collect_pattern = r'collecting\s*\.\.\.\s*([\w/\\]+\.py)'
                collect_match = re.search(collect_pattern, output, re.IGNORECASE)
                if collect_match:
                    source_file = collect_match.group(1)
                    line_num = 1
                else:
                    source_file = None
                    line_num = None
            
            return TestResult(
                test_name=f"pytest_import_error",
                passed=False,
                error_message=f"{error_type}: {error_msg}",
                file_path=source_file,
                line_number=line_num,
                failure_type="IMPORT"
            )
        
        # Look for SyntaxError during collection
        syntax_error = re.search(
            r'SyntaxError:\s*(.*?)(?:\n|$)',
            output
        )
        if syntax_error:
            file_pattern = r'File\s*["\']([^"\']+\.py)["\'],\s*line\s*(\d+)'
            file_match = re.search(file_pattern, output)
            
            if file_match:
                source_file = file_match.group(1)
                line_num = int(file_match.group(2))
            else:
                source_file = None
                line_num = None
            
            return TestResult(
                test_name="pytest_syntax_error",
                passed=False,
                error_message=f"SyntaxError: {syntax_error.group(1)}",
                file_path=source_file,
                line_number=line_num,
                failure_type="SYNTAX"
            )
        
        # Look for assertion failures in short form
        assert_error = re.search(
            r'AssertionError:\s*(.*?)(?:\n|$)',
            output
        )
        if assert_error:
            # Find the source file causing the assertion
            file_pattern = r'([a-zA-Z_][\w]*\.py):(\d+)'
            file_match = re.search(file_pattern, output)
            
            if file_match:
                test_file = file_match.group(1)
                line_num = int(file_match.group(2))
                # Derive source from test file
                if test_file.startswith('test_'):
                    source_file = test_file[5:]
                else:
                    source_file = test_file
            else:
                source_file = None
                line_num = 1
            
            return TestResult(
                test_name="pytest_assertion_error",
                passed=False,
                error_message=f"AssertionError: {assert_error.group(1)}",
                file_path=source_file,
                line_number=line_num,
                failure_type="LOGIC"
            )
        
        # Generic failure - try to extract any useful info
        # Look for "ERRORS" or "FAILED" in summary line
        if 'error' in output.lower() or 'failed' in output.lower():
            print(f"  [TestRunner] _parse_pytest_crash: Generic failure detected, output[:200]={output[:200]}")
            return TestResult(
                test_name="pytest_error",
                passed=False,
                error_message=output[:500] if output else "Unknown pytest error",
                file_path=None,
                line_number=None,
                failure_type="TEST_FAILURE"
            )
        
        # Check if no tests were found/collected
        if 'no tests ran' in output.lower() or 'collected 0 items' in output.lower():
            print(f"  [TestRunner] _parse_pytest_crash: No tests found")
            return TestResult(
                test_name="pytest_no_tests",
                passed=True,  # Not a failure, just no tests
                error_message="No tests found to run",
                file_path=None,
                line_number=None,
                failure_type=None
            )
        
        print(f"  [TestRunner] _parse_pytest_crash: No patterns matched, output[:200]={output[:200]}")
        return None
    
    def _parse_pytest_detailed_output(self, output: str, repo_path: str) -> List[TestResult]:
        """Parse pytest output with detailed failure information"""
        results = []
        import re
        
        # Match test results: test_file.py::test_name PASSED/FAILED
        test_pattern = r'([\w/\\.]+)::(\w+)\s+(PASSED|FAILED|ERROR|SKIPPED)'
        test_matches = re.findall(test_pattern, output)
        
        for match in test_matches:
            file_path, test_name, status = match
            full_test_name = f"{file_path}::{test_name}"
            
            if status == 'PASSED':
                results.append(TestResult(
                    test_name=full_test_name,
                    passed=True,
                    file_path=file_path
                ))
            else:
                # Try to extract failure details including the actual source file
                error_msg, line_number, failure_type, source_file = self._extract_failure_details(
                    output, file_path, test_name, repo_path
                )
                
                # Use source_file (the actual file with the bug) not the test file
                results.append(TestResult(
                    test_name=full_test_name,
                    passed=False,
                    error_message=error_msg,
                    file_path=source_file,  # This is the SOURCE FILE with the bug
                    line_number=line_number,
                    failure_type=failure_type
                ))
        
        return results
    
    def _extract_failure_details(self, output: str, test_file: str, test_name: str, repo_path: str) -> tuple:
        """Extract detailed failure info from pytest output.
        
        Returns: (error_msg, line_number, failure_type, source_file)
        - source_file: The actual file with the bug (may differ from test_file)
        """
        import re
        error_msg = "Test failed"
        line_number = None
        failure_type = "AssertionError"
        source_file = test_file  # Default to test file, but we'll try to find the actual source
        
        # Look for the failure block for this specific test
        # Pattern matches: FAILED test_file.py::test_name - AssertionError: ...
        fail_pattern = rf'FAILED\s+{re.escape(test_file)}::{re.escape(test_name)}\s*[-:]\s*(.*?)(?:\n|$)'
        fail_match = re.search(fail_pattern, output, re.IGNORECASE)
        if fail_match:
            error_msg = fail_match.group(1).strip()[:300]
        
        # Look for assertion details like "AssertionError: assert 6 == 5"
        assertion_detail = re.search(rf'{re.escape(test_name)}.*?AssertionError:\s*(.*?)(?:\n|$)', output, re.DOTALL)
        if assertion_detail:
            error_msg = f"AssertionError: {assertion_detail.group(1).strip()[:200]}"
        
        # Alternative: look for "E       assert" patterns (pytest's detailed assertion output)
        assert_pattern = r'E\s+assert\s+(.*?)$'
        assert_match = re.search(assert_pattern, output, re.MULTILINE)
        if assert_match:
            assert_detail = assert_match.group(1).strip()[:200]
            if '==' in assert_detail or '!=' in assert_detail:
                error_msg = f"AssertionError: assert {assert_detail}"
        
        # Look for "E       AssertionError: ..." pattern with expected/actual
        e_assertion_pattern = r'E\s+AssertionError:\s*(.*?)$'
        e_match = re.search(e_assertion_pattern, output, re.MULTILINE)
        if e_match:
            error_msg = f"AssertionError: {e_match.group(1).strip()[:200]}"
        
        # Capture pytest's "where X = ..." lines for context
        where_pattern = r'E\s+where\s+(.*?)$'
        where_matches = re.findall(where_pattern, output, re.MULTILINE)
        if where_matches:
            where_context = "; where " + "; ".join(w.strip() for w in where_matches[:3])
            error_msg = error_msg + where_context[:150]
        
        # CRITICAL: Find the actual source file that caused the failure
        # Look through the traceback to find non-test files
        # Pattern matches lines like: calculator.py:2: in multiply
        source_pattern = r'([a-zA-Z_][\w/\\]*\.py):(\d+):\s+in\s+(\w+)'
        source_matches = re.findall(source_pattern, output)
        
        print(f"    DEBUG _extract_failure_details: test_file={test_file}, test_name={test_name}")
        print(f"    DEBUG source_matches found: {source_matches}")
        
        # Prioritize non-test source files
        for src_file, src_line, func_name in source_matches:
            # Skip test files - we want the ACTUAL SOURCE FILE with the bug
            if not src_file.startswith('test_') and 'test' not in src_file.lower() and src_file != test_file:
                source_file = src_file
                line_number = int(src_line)
                failure_type = "LOGIC"  # Test failure in source = logic bug
                error_msg = f"Test '{test_name}' failed: logic error in {src_file}:{src_line} function '{func_name}'. {error_msg}"
                print(f"    DEBUG: Found source file from traceback: {source_file}:{line_number}")
                break
        
        # Also try pattern: >       return a + b (where the function is called)
        # Or pattern: calculator.py:2: OperatorError
        if source_file == test_file:
            alt_source_pattern = r'\b([a-zA-Z_]\w*\.py):(\d+)'
            alt_matches = re.findall(alt_source_pattern, output)
            for src_file, src_line in alt_matches:
                if not src_file.startswith('test_') and 'test' not in src_file.lower():
                    source_file = src_file
                    line_number = int(src_line)
                    failure_type = "LOGIC"
                    print(f"    DEBUG: Found source file from alt pattern: {source_file}:{line_number}")
                    break
        
        # If we still haven't found a source file, try to derive from test file name
        # test_calculator.py -> calculator.py
        # Also handle paths like tests/test_calculator.py -> calculator.py
        if source_file == test_file:
            import os as os_module
            test_basename = os_module.path.basename(test_file)  # tests/test_calculator.py -> test_calculator.py
            
            if test_basename.startswith('test_'):
                potential_source = test_basename[5:]  # Remove 'test_' prefix: test_calculator.py -> calculator.py
                source_file = potential_source
                failure_type = "LOGIC"
                # Default to line 1 if no line found
                if line_number is None:
                    line_number = 1
                print(f"    DEBUG: Derived source file from test name: {test_file} -> {source_file}")
            elif test_basename.endswith('_test.py'):
                potential_source = test_basename.replace('_test.py', '.py')  # calculator_test.py -> calculator.py
                source_file = potential_source
                failure_type = "LOGIC"
                if line_number is None:
                    line_number = 1
                print(f"    DEBUG: Derived source file from test name: {test_file} -> {source_file}")
        
        # If we didn't find a source file, look for the test file line
        if source_file == test_file and line_number is None:
            line_pattern = rf'[\\/]?({re.escape(test_file)}):(\d+):'
            line_match = re.search(line_pattern, output)
            if line_match:
                line_number = int(line_match.group(2))
        
        # Final fallback - default line 1 if still None
        if line_number is None:
            line_number = 1
        
        return error_msg, line_number, failure_type, source_file
    
    def _parse_pytest_output(self, output: str) -> List[TestResult]:
        """Parse pytest JSON output"""
        results = []
        try:
            import json
            # Try to find JSON in output
            lines = output.split('\n')
            for line in lines:
                if line.strip().startswith('{'):
                    try:
                        data = json.loads(line.strip())
                        if 'tests' in data:
                            for test in data['tests']:
                                results.append(TestResult(
                                    test_name=test.get('nodeid', 'unknown'),
                                    passed=test.get('outcome') == 'passed',
                                    error_message=test.get('longrepr', None),
                                    duration=test.get('duration', None)
                                ))
                    except:
                        pass
        except:
            pass
        return results
    
    def _parse_pytest_verbose_output(self, output: str) -> List[TestResult]:
        """Parse pytest verbose output"""
        results = []
        import re
        
        # Match lines like: test_file.py::test_name PASSED/FAILED
        pattern = r'([\w/\\.]+)::(\w+)\s+(PASSED|FAILED|ERROR|SKIPPED)'
        matches = re.findall(pattern, output)
        
        for match in matches:
            test_file, test_name, status = match
            full_test_name = f"{test_file}::{test_name}"
            
            if status == 'PASSED':
                results.append(TestResult(
                    test_name=full_test_name,
                    passed=True,
                    file_path=test_file
                ))
            else:
                # Try to derive source file from test file name
                if test_file.startswith('test_'):
                    source_file = test_file[5:]  # test_calculator.py -> calculator.py
                else:
                    source_file = test_file
                
                results.append(TestResult(
                    test_name=full_test_name,
                    passed=False,
                    error_message=f"Test {status}",
                    file_path=source_file,
                    line_number=1,  # Default to line 1
                    failure_type="AssertionError"
                ))
        
        return results
    
    async def _run_unittest(self, repo_path: str) -> List[TestResult]:
        """Run unittest tests"""
        results = []
        
        try:
            process = await asyncio.create_subprocess_exec(
                'python', '-m', 'unittest', 'discover', '-v',
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
            output = stderr.decode('utf-8', errors='ignore')  # unittest outputs to stderr
            
            # Parse output
            import re
            pattern = r'(test_\w+)\s+\(([\w.]+)\)\s+\.\.\.\s+(ok|FAIL|ERROR)'
            matches = re.findall(pattern, output)
            
            for match in matches:
                test_name, test_class, status = match
                results.append(TestResult(
                    test_name=f"{test_class}.{test_name}",
                    passed=status == 'ok',
                    error_message=None if status == 'ok' else f"Test {status}"
                ))
                
        except asyncio.TimeoutError:
            results = [TestResult(
                test_name="unittest_timeout",
                passed=False,
                error_message="Test execution timed out after 5 minutes"
            )]
        except Exception as e:
            results = [TestResult(
                test_name="unittest_error",
                passed=False,
                error_message=str(e)
            )]
        
        return results
    
    async def _run_npm_tests(self, repo_path: str, framework: str) -> List[TestResult]:
        """Run npm-based tests (jest, vitest, mocha)"""
        results = []
        
        try:
            # First, install dependencies if needed
            if not os.path.exists(os.path.join(repo_path, 'node_modules')):
                install_process = await asyncio.create_subprocess_exec(
                    'npm', 'install',
                    cwd=repo_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await asyncio.wait_for(install_process.communicate(), timeout=300)
            
            # Run tests
            process = await asyncio.create_subprocess_exec(
                'npm', 'test', '--', '--reporter=json' if framework != 'mocha' else '',
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
            output = stdout.decode('utf-8', errors='ignore')
            
            # Simple parsing for now
            if process.returncode == 0:
                results.append(TestResult(
                    test_name="npm_test_suite",
                    passed=True,
                    error_message=None
                ))
            else:
                results.append(TestResult(
                    test_name="npm_test_suite",
                    passed=False,
                    error_message=stderr.decode('utf-8', errors='ignore')[:500]
                ))
                
        except asyncio.TimeoutError:
            results = [TestResult(
                test_name="npm_test_timeout",
                passed=False,
                error_message="Test execution timed out after 5 minutes"
            )]
        except Exception as e:
            results = [TestResult(
                test_name="npm_test_error",
                passed=False,
                error_message=str(e)
            )]
        
        return results
