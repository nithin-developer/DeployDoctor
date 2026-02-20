"""
Orchestrator Agent - Coordinates all agents and manages the analysis workflow
Multi-agent system for comprehensive code analysis, testing, and fixing with iterative repair
"""
import os
import shutil
import asyncio
from datetime import datetime
from typing import Any, Dict, Callable, List, Optional
from dataclasses import dataclass, field
from git import Repo
from agents.base_agent import BaseAgent
from agents.code_review_agent import CodeReviewAgent
from agents.test_runner_agent import TestRunnerAgent
from agents.sandbox_executor_agent import SandboxExecutorAgent
from agents.code_fixer_agent import CodeFixerAgent
from agents.test_generator_agent import TestGeneratorAgent
from analysis_schemas import AnalysisRequest, AnalysisResult, CodeFix, FixStatus, BugType, GeneratedTest, CIStatusEnum
from utils.git_manager import GitManager
from services.github_service import github_service
from config import settings


@dataclass
class IterationSummary:
    """Summary of a single fix iteration"""
    iteration: int
    errors_before: int
    errors_after: int
    fixes_attempted: int
    fixes_successful: int
    time_taken: float
    errors_fixed: List[str] = field(default_factory=list)
    errors_remaining: List[str] = field(default_factory=list)


@dataclass
class AnalysisSummary:
    """Comprehensive analysis summary"""
    total_iterations: int
    initial_errors: int
    final_errors: int
    total_fixes_attempted: int
    total_fixes_successful: int
    total_time: float
    iterations: List[IterationSummary] = field(default_factory=list)
    all_errors_found: List[Dict] = field(default_factory=list)
    infrastructure_errors: List[Dict] = field(default_factory=list)
    code_review_issues: int = 0  # Count from code review (may overlap with errors)
    resolution_status: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "total_iterations": self.total_iterations,
            "initial_errors": self.initial_errors,
            "final_errors": self.final_errors,
            "errors_resolved": self.initial_errors - self.final_errors,
            "total_fixes_attempted": self.total_fixes_attempted,
            "total_fixes_successful": self.total_fixes_successful,
            "code_review_issues": self.code_review_issues,
            "total_time_seconds": round(self.total_time, 2),
            "resolution_status": self.resolution_status,
            "iterations": [
                {
                    "iteration": it.iteration,
                    "errors_before": it.errors_before,
                    "errors_after": it.errors_after,
                    "fixes_attempted": it.fixes_attempted,
                    "fixes_successful": it.fixes_successful,
                    "time_seconds": round(it.time_taken, 2),
                    "errors_fixed": it.errors_fixed,
                    "errors_remaining": it.errors_remaining
                }
                for it in self.iterations
            ],
            "all_errors_found": self.all_errors_found,
            "infrastructure_errors": self.infrastructure_errors
        }


class OrchestratorAgent(BaseAgent):
    """
    Main orchestrator that coordinates all analysis agents with iterative fixing.
    
    Workflow:
    1. Clone repository
    2. Run sandbox executor to detect runtime errors
    3. Run code review agent for line-by-line analysis  
    4. Iteratively fix issues until all resolved or max iterations reached
    5. Run tests to verify
    6. Generate comprehensive summary report
    """
    
    MAX_ITERATIONS = 5  # Maximum fix-verify iterations
    
    def __init__(self, progress_callback: Callable[[str, int, str], None] = None):
        super().__init__(
            name="Orchestrator Agent",
            description="I coordinate the multi-agent analysis workflow with iterative fixing until all issues are resolved."
        )
        self.sandbox_agent = SandboxExecutorAgent()
        self.code_review_agent = CodeReviewAgent()
        self.code_fixer_agent = CodeFixerAgent()
        self.test_runner_agent = TestRunnerAgent()
        self.test_generator_agent = TestGeneratorAgent()
        self.progress_callback = progress_callback
    
    def _report_progress(self, status: str, progress: int, message: str):
        """Report progress to callback if available"""
        if self.progress_callback:
            self.progress_callback(status, progress, message)
    
    def _get_error_signature(self, error) -> str:
        """Get a unique signature for an error"""
        error_file = getattr(error, 'error_file', 'unknown')
        error_line = getattr(error, 'error_line', '?')
        error_type = getattr(error, 'error_type', 'Error')
        return f"{error_type} in {error_file}:{error_line}"
    
    def _is_infrastructure_error(self, error) -> bool:
        """Check if error is infrastructure-related (not fixable in code)"""
        error_type = getattr(error, 'error_type', '')
        error_file = getattr(error, 'error_file', None)
        
        # Infrastructure error types that aren't code issues
        infra_types = {'DOCKER_ERROR', 'TIMEOUT', 'SETUP_ERROR', 'ENVIRONMENT_ERROR'}
        
        if error_type in infra_types:
            return True
        
        # Errors without a file can't be fixed in code
        if error_file is None or error_file == 'None' or error_file == 'unknown':
            return True
            
        return False
    
    def _filter_fixable_errors(self, errors) -> tuple:
        """Separate fixable code errors from infrastructure errors"""
        fixable = []
        infra = []
        for err in errors:
            if self._is_infrastructure_error(err):
                infra.append(err)
            else:
                fixable.append(err)
        return fixable, infra
    
    def _error_to_dict(self, error) -> Dict:
        """Convert execution error to dictionary"""
        return {
            "file": getattr(error, 'error_file', None),
            "line": getattr(error, 'error_line', None),
            "type": getattr(error, 'error_type', 'Error'),
            "message": getattr(error, 'stderr', '')[:200]
        }
    
    def _test_failure_to_error(self, test_result) -> Dict:
        """Convert a failed test result to an error dict for the fixer"""
        return {
            "file_path": test_result.file_path,
            "line_number": test_result.line_number,
            "bug_type": "TEST_FAILURE",
            "description": f"Test '{test_result.test_name}' failed: {test_result.error_message or 'Unknown error'}",
            "failure_type": test_result.failure_type or "AssertionError"
        }
    
    def _create_test_error_object(self, test_result, repo_path: str):
        """Create an error-like object from test failure for the fix iteration"""
        class TestError:
            def __init__(self, test_result, repo_path):
                self.error_file = test_result.file_path
                self.error_line = test_result.line_number
                self.error_type = "TEST_FAILURE"
                self.stderr = f"Test '{test_result.test_name}' failed: {test_result.error_message or 'assertion failed'}"
                self.success = False
        return TestError(test_result, repo_path)
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the full multi-agent analysis workflow with iterative fixing"""
        request: AnalysisRequest = context.get("request")
        
        start_time = datetime.now()
        self._report_progress("running", 5, "Initializing analysis...")
        
        # Create temp directory
        os.makedirs(settings.TEMP_REPO_DIR, exist_ok=True)
        
        # Generate branch name
        team_name_slug = request.team_name.upper().replace(" ", "_")
        leader_name_slug = request.team_leader_name.replace(" ", "_")
        branch_name = f"{team_name_slug}_{leader_name_slug}_AI_Fix"
        
        repo_path = None
        all_fixes: List[CodeFix] = []
        generated_tests: List[GeneratedTest] = []
        commit_sha: Optional[str] = None
        branch_url: Optional[str] = None
        commit_message: Optional[str] = None
        pr_url: Optional[str] = None
        pr_number: Optional[int] = None
        ci_status: Optional[CIStatusEnum] = None
        summary = AnalysisSummary(
            total_iterations=0,
            initial_errors=0,
            final_errors=0,
            total_fixes_attempted=0,
            total_fixes_successful=0,
            total_time=0
        )
        
        try:
            # Step 1: Clone repository
            self._report_progress("running", 10, "Cloning repository...")
            repo_path = await self._clone_repository(request.repo_url)
            
            if not repo_path:
                return self._create_error_result(
                    request, branch_name, start_time, 
                    "Failed to clone repository. Check if the URL is correct and the repository is public."
                )
            
            # Create analysis context
            analysis_context = {
                "repo_path": repo_path,
                "request": request
            }
            
            # Step 2: Initial sandbox execution to detect runtime errors
            self._report_progress("running", 15, "Running code in sandbox to detect runtime errors...")
            sandbox_result = await self.sandbox_agent.execute(analysis_context)
            all_errors = [r for r in sandbox_result.get("execution_results", []) 
                            if not getattr(r, 'success', True)]
            
            # Separate fixable code errors from infrastructure errors
            current_errors, infra_errors = self._filter_fixable_errors(all_errors)
            
            # Track which errors have been fixed (by signature) to avoid re-fixing
            fixed_error_signatures = set()
            
            initial_error_count = len(current_errors)
            summary.initial_errors = initial_error_count
            
            if infra_errors:
                print(f"\nNote: {len(infra_errors)} infrastructure errors detected (Docker not available, etc.)")
                for err in infra_errors:
                    print(f"  - {self._get_error_signature(err)} (not fixable in code)")
                    summary.infrastructure_errors.append(self._error_to_dict(err))
            
            # Record all initial errors
            for err in current_errors:
                summary.all_errors_found.append(self._error_to_dict(err))
            
            print(f"\n{'='*60}")
            print(f"INITIAL ANALYSIS: Found {initial_error_count} execution errors")
            for err in current_errors:
                print(f"  - {self._get_error_signature(err)}")
            print(f"{'='*60}\n")
            
            # Step 3: Run comprehensive code review
            self._report_progress("running", 25, "Analyzing code line by line...")
            review_result = await self.code_review_agent.execute(analysis_context)
            code_issues = review_result.get("issues", [])
            
            # Track code review issues count
            summary.code_review_issues = len(code_issues)
            
            # Add code review issues to all_errors_found
            for issue in code_issues:
                summary.all_errors_found.append({
                    "file": issue.get("file_path"),
                    "line": issue.get("line_number"),
                    "type": issue.get("bug_type", "LINTING"),
                    "message": issue.get("description", "Code review issue detected")
                })
            
            # Deduplicate code review issues that overlap with sandbox errors
            seen_locations = set()
            for err in current_errors:
                err_sig = f"{getattr(err, 'error_file', '')}:{getattr(err, 'error_line', '')}"
                seen_locations.add(err_sig)
            
            unique_code_issues = []
            for issue in code_issues:
                issue_sig = f"{issue.get('file_path', '')}:{issue.get('line_number', '')}"
                if issue_sig not in seen_locations:
                    unique_code_issues.append(issue)
                    seen_locations.add(issue_sig)
            
            print(f"Code review found {len(code_issues)} issues ({len(unique_code_issues)} unique after dedup)")
            
            # Step 3.5: Generate AI tests BEFORE the fix loop (if requested)
            # This ensures AI-generated tests are run during iterations
            generated_tests = []
            if request.generate_tests:
                self._report_progress("running", 28, "Generating AI test cases...")
                try:
                    test_gen_context = {
                        "repo_path": repo_path,
                        "test_framework": "pytest"
                    }
                    test_gen_result = await self.test_generator_agent.execute(test_gen_context)
                    generated_tests = test_gen_result.get("generated_tests", [])
                    print(f"Generated {len(generated_tests)} AI test cases (will be run during iteration)")
                except Exception as e:
                    print(f"Test generation warning: {e} - will continue without AI tests")
                    generated_tests = []
            
            # Step 4: ITERATIVE FIX LOOP
            # Continue while there are errors OR tests are failing (up to MAX_ITERATIONS)
            iteration = 0
            progress_per_iteration = 50 / self.MAX_ITERATIONS  # Spread across 25-75%
            tests_passing = False  # Track if tests pass
            
            # Always run at least one iteration if there are errors or code issues
            # Continue while: (have errors OR tests failing OR have unfixed code issues) AND under max iterations
            while iteration < self.MAX_ITERATIONS:
                iteration += 1
                iteration_start = datetime.now()
                skipped_logic_issues = []  # Initialize for this iteration
                
                # Filter out errors that have already been fixed in previous iterations
                unfixed_errors = [e for e in current_errors 
                                 if self._get_error_signature(e) not in fixed_error_signatures]
                
                if not unfixed_errors:
                    print(f"\n--- ITERATION {iteration} ---")
                    print(f"  DEBUG: unfixed_errors is empty, unique_code_issues count: {len(unique_code_issues)}")
                    print("  All known errors have been addressed - verifying...")
                    # Re-run sandbox to check for new errors
                    verification_result = await self.sandbox_agent.execute(analysis_context)
                    all_new_errors = [r for r in verification_result.get("execution_results", []) 
                                     if not getattr(r, 'success', True)]
                    current_errors, _ = self._filter_fixable_errors(all_new_errors)
                    
                    # Also run tests to verify
                    test_result = await self.test_runner_agent.execute(analysis_context)
                    test_failures = [t for t in test_result.get("test_results", []) if not t.passed]
                    
                    if not current_errors and not test_failures:
                        print("  ✓ All errors resolved and tests pass!")
                        break
                    elif test_failures:
                        print(f"  ⚠ Tests still failing: {len(test_failures)}")
                        # Convert test failures to errors for fixing
                        test_failure_converted = False
                        for tf in test_failures:
                            file_path = tf.file_path
                            print(f"    DEBUG: test failure - name={tf.test_name}, file_path={tf.file_path}")
                            
                            # Handle generic pytest_error cases - try to find source from error message
                            if tf.test_name in ['pytest_error', 'pytest_parse_error', 'pytest_assertion_error']:
                                # Try to extract file from error message
                                import re
                                file_match = re.search(r'([a-zA-Z_]\w*\.py)', tf.error_message or '')
                                if file_match:
                                    potential_file = file_match.group(1)
                                    if not potential_file.startswith('test_'):
                                        file_path = potential_file
                                        print(f"    Derived file_path from error message: {file_path}")
                            
                            # Try to derive file_path from test name
                            if not file_path and tf.test_name:
                                if '::' in tf.test_name:
                                    test_file = tf.test_name.split('::')[0]
                                else:
                                    test_file = tf.test_name
                                # Handle paths like "tests/test_calculator.py" - extract basename
                                import os as os_module
                                test_basename = os_module.path.basename(test_file)
                                # test_calculator.py -> calculator.py
                                if test_basename.startswith('test_'):
                                    file_path = test_basename[5:]
                                elif test_basename.endswith('_test.py'):
                                    file_path = test_basename.replace('_test.py', '.py')
                                print(f"    Derived file_path from test name: {test_file} -> {file_path}")
                            
                            if file_path:
                                tf.file_path = file_path
                                tf.line_number = tf.line_number or 1
                                test_error = self._create_test_error_object(tf, repo_path)
                                current_errors.append(test_error)
                                test_failure_converted = True
                            else:
                                print(f"    Warning: Could not derive source file for test failure: {tf.test_name}")
                        
                        # Decide whether to continue, break, or fall through
                        if test_failure_converted:
                            # We converted test failures to errors - continue to next iteration to fix them
                            continue
                        elif unique_code_issues:
                            # Couldn't convert test failures but have LOGIC issues to try
                            print(f"  ⚠ No test error file info but have {len(unique_code_issues)} code review issues to process")
                            # Fall through to process unique_code_issues
                        else:
                            print("  ⚠ Tests failing but cannot determine source files - stopping")
                            break
                    else:
                        # No test failures and no current errors - sanity check failed, continue
                        continue
                
                progress = 25 + int(iteration * progress_per_iteration)
                self._report_progress("running", progress, 
                    f"Fix iteration {iteration}/{self.MAX_ITERATIONS}: Attempting to fix {len(unfixed_errors)} errors...")
                
                print(f"\n--- ITERATION {iteration} ---")
                print(f"Errors to fix: {len(unfixed_errors)} (total remaining: {len(current_errors)})")
                print(f"  DEBUG: unique_code_issues count: {len(unique_code_issues)}")
                
                # Log what issues we're about to process
                for i, issue in enumerate(unique_code_issues[:5]):  # Show first 5
                    print(f"    issue[{i}]: {issue.get('bug_type')} in {issue.get('file_path')}:{issue.get('line_number')}")
                
                errors_before = len(current_errors)
                error_signatures_before = set(self._get_error_signature(e) for e in current_errors)
                
                # Prepare context for fixer (only include unfixed errors with proper error info)
                valid_errors = [e for e in unfixed_errors 
                              if getattr(e, 'error_file', None) and getattr(e, 'stderr', '')]
                
                if not valid_errors and not unique_code_issues:
                    # No execution errors or code issues to fix
                    # But we might have test failures - run tests to check
                    test_result = await self.test_runner_agent.execute(analysis_context)
                    test_failures = [t for t in test_result.get("test_results", []) if not t.passed]
                    
                    if test_failures:
                        print(f"  No execution errors, but {len(test_failures)} tests failing - converting to errors")
                        # Convert test failures to fixable errors
                        for tf in test_failures:
                            file_path = tf.file_path
                            if not file_path and tf.test_name and '::' in tf.test_name:
                                test_file = tf.test_name.split('::')[0]
                                # Handle paths like "tests/test_calculator.py" - extract basename
                                import os as os_module
                                test_basename = os_module.path.basename(test_file)
                                if test_basename.startswith('test_'):
                                    file_path = test_basename[5:]
                                elif test_basename.endswith('_test.py'):
                                    file_path = test_basename.replace('_test.py', '.py')
                                else:
                                    file_path = test_basename
                            if file_path:
                                tf.file_path = file_path
                                tf.line_number = tf.line_number or 1
                                test_error = self._create_test_error_object(tf, repo_path)
                                current_errors.append(test_error)
                                valid_errors.append(test_error)
                        
                        if not valid_errors:
                            print("  Could not extract source files from test failures - stopping")
                            break
                    else:
                        print("  All tests pass and no errors - iteration complete!")
                        tests_passing = True
                        break
                
                fixer_context = {
                    "repo_path": repo_path,
                    "issues": unique_code_issues,  # Pass unfixed code issues on every iteration
                    "execution_errors": valid_errors
                }
                
                # Run fixer
                fix_result = await self.code_fixer_agent.execute(fixer_context)
                iteration_fixes = fix_result.get("fixes", [])
                
                # Get skipped LOGIC issues to process in next iteration
                skipped_logic_issues = fix_result.get("skipped_logic_issues", [])
                if skipped_logic_issues:
                    print(f"  {len(skipped_logic_issues)} LOGIC issues deferred to next iteration")
                
                fixes_attempted = len(iteration_fixes)
                fixes_successful = sum(1 for f in iteration_fixes if f.status == FixStatus.FIXED)
                
                all_fixes.extend(iteration_fixes)
                summary.total_fixes_attempted += fixes_attempted
                summary.total_fixes_successful += fixes_successful
                
                print(f"  Fixes attempted: {fixes_attempted}, Successful: {fixes_successful}")
                
                # Verify fixes by re-running sandbox
                self._report_progress("running", progress + 3, 
                    f"Iteration {iteration}: Verifying syntax/runtime errors...")
                
                verification_result = await self.sandbox_agent.execute(analysis_context)
                all_new_errors = [r for r in verification_result.get("execution_results", []) 
                                 if not getattr(r, 'success', True)]
                current_errors, _ = self._filter_fixable_errors(all_new_errors)
                
                # ALSO run tests to verify fixes actually work correctly
                self._report_progress("running", progress + 5, 
                    f"Iteration {iteration}: Running tests to verify fixes...")
                
                test_result = await self.test_runner_agent.execute(analysis_context)
                test_failures = [t for t in test_result.get("test_results", []) if not t.passed]
                
                print(f"  Tests: {test_result.get('passed', 0)} passed, {test_result.get('failed', 0)} failed")
                
                # Convert test failures to errors that can be fixed in next iteration
                for tf in test_failures:
                    # Get file_path - if not set or empty, try to extract from test name
                    file_path = tf.file_path if tf.file_path and tf.file_path.strip() else None
                    
                    print(f"    Debug: Processing test failure - test_name={tf.test_name}, file_path={tf.file_path}, line={tf.line_number}")
                    
                    if not file_path and tf.test_name and '::' in tf.test_name:
                        # Extract source file from test name like "tests/test_calculator.py::test_multiply"
                        test_file = tf.test_name.split('::')[0]
                        
                        # Handle paths like "tests/test_calculator.py" - extract basename first
                        import os as os_module
                        test_basename = os_module.path.basename(test_file)
                        
                        # Try to find corresponding source file (test_calculator.py -> calculator.py)
                        if test_basename.startswith('test_'):
                            file_path = test_basename[5:]  # Remove 'test_' prefix: test_calculator.py -> calculator.py
                        elif test_basename.endswith('_test.py'):
                            file_path = test_basename.replace('_test.py', '.py')  # calculator_test.py -> calculator.py
                        else:
                            file_path = test_basename
                        print(f"    Debug: Derived file_path from test name: {test_file} -> {file_path}")
                    
                    if file_path:
                        # Default to line 1 if line_number not found
                        line_num = tf.line_number if tf.line_number else 1
                        
                        # Update the test_result with calculated values
                        tf.file_path = file_path
                        tf.line_number = line_num
                        
                        test_error = self._create_test_error_object(tf, repo_path)
                        current_errors.append(test_error)
                        # Add to all_errors_found for tracking
                        summary.all_errors_found.append({
                            "file": file_path,
                            "line": line_num,
                            "type": "TEST_FAILURE",
                            "message": tf.error_message or "Test failed"
                        })
                        print(f"    ⚠ Test failure added: {file_path}:{line_num} - {tf.error_message}")
                    else:
                        # Still log the failure even without file info - try to extract any useful info
                        test_file = tf.test_name.split('::')[0] if '::' in tf.test_name else tf.test_name
                        # Handle paths like "tests/test_calculator.py" - extract basename
                        import os as os_module
                        test_basename = os_module.path.basename(test_file)
                        
                        if test_basename.startswith('test_'):
                            potential_source = test_basename[5:]  # test_calculator.py -> calculator.py
                        elif test_basename.endswith('_test.py'):
                            potential_source = test_basename.replace('_test.py', '.py')
                        else:
                            potential_source = test_basename
                            
                        if potential_source and potential_source.endswith('.py'):
                            file_path = potential_source
                            line_num = 1
                            tf.file_path = file_path
                            tf.line_number = line_num
                            test_error = self._create_test_error_object(tf, repo_path)
                            current_errors.append(test_error)
                            summary.all_errors_found.append({
                                "file": file_path,
                                "line": line_num,
                                "type": "TEST_FAILURE",
                                "message": tf.error_message or "Test failed"
                            })
                            print(f"    ⚠ Test failure (best-effort source): {file_path}:{line_num} - {tf.error_message}")
                        else:
                            print(f"    ⚠ Test failure (no source file detected): {tf.test_name} - {tf.error_message}")
                
                errors_after = len(current_errors)
                error_signatures_after = set(self._get_error_signature(e) for e in current_errors)
                
                # Determine which errors were fixed and which remain
                errors_fixed = list(error_signatures_before - error_signatures_after)
                errors_remaining = list(error_signatures_after)
                
                # Add fixed errors to the tracking set to avoid re-fixing
                fixed_error_signatures.update(errors_fixed)
                
                iteration_time = (datetime.now() - iteration_start).total_seconds()
                
                # Record iteration summary
                iter_summary = IterationSummary(
                    iteration=iteration,
                    errors_before=errors_before,
                    errors_after=errors_after,
                    fixes_attempted=fixes_attempted,
                    fixes_successful=fixes_successful,
                    time_taken=iteration_time,
                    errors_fixed=errors_fixed,
                    errors_remaining=errors_remaining
                )
                summary.iterations.append(iter_summary)
                
                print(f"  Result: {errors_before} errors -> {errors_after} errors (including test failures)")
                if errors_fixed:
                    print(f"  ✓ Fixed: {errors_fixed}")
                if errors_remaining:
                    print(f"  ⚠ Remaining: {errors_remaining}")
                print(f"  Time: {iteration_time:.2f}s")
                
                # Update unique_code_issues with skipped LOGIC issues for next iteration
                # This ensures LOGIC issues are processed after SYNTAX is fixed
                unique_code_issues = skipped_logic_issues if skipped_logic_issues else []
                
                # If no improvement AND tests are passing, break early
                if errors_after >= errors_before and fixes_successful == 0 and fixes_attempted > 0:
                    if len(test_failures) == 0:
                        print(f"\n  No progress made but tests pass - stopping iterations")
                        tests_passing = True
                        break
                    else:
                        print(f"\n  ⚠ No progress on errors but {len(test_failures)} tests still failing - continuing")
                
                # Success: no errors and no test failures
                if errors_after == 0 and len(test_failures) == 0:
                    print(f"\n  ✓ All errors fixed and tests pass!")
                    tests_passing = True
                    break
            
            summary.total_iterations = iteration
            summary.final_errors = len(current_errors)
            
            # Determine resolution status
            if summary.final_errors == 0:
                summary.resolution_status = "ALL_RESOLVED"
            elif summary.final_errors < summary.initial_errors:
                summary.resolution_status = "PARTIALLY_RESOLVED"
            else:
                summary.resolution_status = "UNRESOLVED"
            
            # Step 5: Run final tests and iterate if needed
            self._report_progress("running", 80, "Running final tests...")
            test_result = await self.test_runner_agent.execute(analysis_context)
            test_results = test_result.get("test_results", [])
            
            # Log final test results for debugging
            print(f"\n--- FINAL TEST RESULTS ---")
            print(f"  Total: {len(test_results)} results")
            print(f"  Passed: {test_result.get('passed', 0)}")
            print(f"  Failed: {test_result.get('failed', 0)}")
            for tr in test_results:
                status = "✓" if tr.passed else "✗"
                print(f"  {status} {tr.test_name}: {tr.error_message[:100] if tr.error_message else 'OK'}")
            
            # Step 5.5: If tests still failing, do additional fix iterations focused on test failures
            final_test_iterations = 0
            max_final_iterations = 3
            
            while test_result.get('failed', 0) > 0 and final_test_iterations < max_final_iterations:
                final_test_iterations += 1
                print(f"\n--- TEST FIX ITERATION {final_test_iterations} ---")
                
                # Convert test failures to errors
                test_errors = []
                for tf in [t for t in test_results if not t.passed]:
                    file_path = tf.file_path
                    if not file_path and tf.test_name and '::' in tf.test_name:
                        test_file = tf.test_name.split('::')[0]
                        # Handle paths like "tests/test_calculator.py" - extract basename
                        import os as os_module
                        test_basename = os_module.path.basename(test_file)
                        if test_basename.startswith('test_'):
                            file_path = test_basename[5:]
                        elif test_basename.endswith('_test.py'):
                            file_path = test_basename.replace('_test.py', '.py')
                        else:
                            file_path = test_basename
                    
                    if file_path:
                        tf.file_path = file_path
                        tf.line_number = tf.line_number or 1
                        test_error = self._create_test_error_object(tf, repo_path)
                        test_errors.append(test_error)
                
                if not test_errors:
                    print("  Could not extract source files from test failures - stopping test fix iterations")
                    break
                
                # Deduplicate test errors by file - multiple test failures in same file should be one fix
                seen_files = set()
                deduped_test_errors = []
                for te in test_errors:
                    if te.error_file not in seen_files:
                        seen_files.add(te.error_file)
                        deduped_test_errors.append(te)
                
                print(f"  Deduped: {len(test_errors)} test failures -> {len(deduped_test_errors)} unique source files")
                
                # Run fixer on test errors
                fixer_context = {
                    "repo_path": repo_path,
                    "issues": [],  # No code review issues, just test errors
                    "execution_errors": deduped_test_errors
                }
                
                fix_result = await self.code_fixer_agent.execute(fixer_context)
                iteration_fixes = fix_result.get("fixes", [])
                fixes_successful = sum(1 for f in iteration_fixes if f.status == FixStatus.FIXED)
                
                print(f"  Applied {fixes_successful}/{len(iteration_fixes)} fixes for test failures")
                
                all_fixes.extend(iteration_fixes)
                summary.total_fixes_attempted += len(iteration_fixes)
                summary.total_fixes_successful += fixes_successful
                
                if fixes_successful == 0:
                    print("  No fixes applied - stopping test fix iterations")
                    break
                
                # Re-run tests
                test_result = await self.test_runner_agent.execute(analysis_context)
                test_results = test_result.get("test_results", [])
                print(f"  Tests after fix: {test_result.get('passed', 0)} passed, {test_result.get('failed', 0)} failed")
            
            # Step 6: Tests already generated earlier (skip if already done)
            # generated_tests was set in Step 3.5
            
            # Step 7: Push to GitHub if requested
            if request.push_to_github and request.github_token and all_fixes:
                self._report_progress("running", 90, "Pushing fixes to GitHub...")
                try:
                    git_manager = GitManager(repo_path, request.github_token)
                    
                    # Create fix branch with proper naming: TEAM_NAME_LeaderName_AI_Fix
                    branch_name = git_manager.create_fix_branch(request.team_name, request.team_leader_name)
                    
                    # Stage and commit changes
                    git_manager.stage_all_changes()
                    
                    # Generate detailed commit message
                    fixed_files = list(set(f.file_path for f in all_fixes if f.status == FixStatus.FIXED))
                    bug_types_fixed = list(set(str(f.bug_type.value) if hasattr(f.bug_type, 'value') else str(f.bug_type) for f in all_fixes if f.status == FixStatus.FIXED))
                    
                    commit_message = (
                        f"fix: Auto-fix {summary.total_fixes_successful} bugs in {len(fixed_files)} files\n\n"
                        f"Team: {request.team_name}\n"
                        f"Author: {request.team_leader_name}\n"
                        f"Branch: {branch_name}\n\n"
                        f"Summary:\n"
                        f"- Initial errors: {summary.initial_errors}\n"
                        f"- Errors fixed: {summary.initial_errors - summary.final_errors}\n"
                        f"- Remaining errors: {summary.final_errors}\n"
                        f"- Bug types fixed: {', '.join(bug_types_fixed)}\n"
                        f"- Resolution: {summary.resolution_status}\n"
                        f"- Iterations: {summary.total_iterations}\n"
                        f"- Total time: {summary.total_time:.2f}s\n\n"
                        f"Files modified:\n"
                    )
                    for fp in fixed_files[:10]:  # Limit to 10 files in message
                        commit_message += f"  - {fp}\n"
                    if len(fixed_files) > 10:
                        commit_message += f"  - ... and {len(fixed_files) - 10} more files\n"
                    
                    commit_message += f"\nGenerated by AI Repository Analyser"
                    
                    commit_sha = git_manager.commit_changes(commit_message)
                    
                    # Push to remote
                    push_success, push_result = git_manager.push_to_remote(branch_name)
                    if push_success:
                        branch_url = push_result
                        print(f"Successfully pushed to: {branch_url}")
                        
                        # Step 7.5: Create PR if requested
                        if request.create_pr and request.github_token:
                            self._report_progress("running", 92, "Creating pull request...")
                            try:
                                pr_title = f"[AI Fix] Auto-fix {summary.total_fixes_successful} bugs - {request.team_name}"
                                pr_body = (
                                    f"## 🤖 AI Auto-Fix Pull Request\n\n"
                                    f"**Team:** {request.team_name}\n"
                                    f"**Author:** {request.team_leader_name}\n"
                                    f"**Branch:** `{branch_name}`\n\n"
                                    f"### Summary\n"
                                    f"- **Initial errors:** {summary.initial_errors}\n"
                                    f"- **Errors fixed:** {summary.initial_errors - summary.final_errors}\n"
                                    f"- **Remaining errors:** {summary.final_errors}\n"
                                    f"- **Resolution:** {summary.resolution_status}\n"
                                    f"- **Iterations:** {summary.total_iterations}\n"
                                    f"- **Total time:** {summary.total_time:.2f}s\n\n"
                                    f"### Files Modified\n"
                                )
                                fixed_files = list(set(f.file_path for f in all_fixes if f.status == FixStatus.FIXED))
                                for fp in fixed_files[:15]:
                                    pr_body += f"- `{fp}`\n"
                                if len(fixed_files) > 15:
                                    pr_body += f"- ... and {len(fixed_files) - 15} more files\n"
                                pr_body += f"\n---\n*Generated by AI Repository Analyser*"
                                
                                # Parse repo URL to get owner and repo
                                owner, repo_name = github_service.parse_repo_url(request.repo_url)
                                pr_result = await github_service.create_pull_request(
                                    owner=owner,
                                    repo=repo_name,
                                    head_branch=branch_name,
                                    title=pr_title,
                                    body=pr_body
                                )
                                
                                if pr_result.success:
                                    pr_url = pr_result.pr_url
                                    pr_number = pr_result.pr_number
                                    ci_status = CIStatusEnum.PENDING
                                    print(f"Successfully created PR #{pr_number}: {pr_url}")
                                    
                                    # Start async CI monitoring if auto-merge is enabled
                                    if request.auto_merge_on_ci_success:
                                        print("Starting CI monitoring in background...")
                                        asyncio.create_task(
                                            github_service.poll_ci_and_merge(
                                                repo_url=request.repo_url,
                                                branch_name=branch_name,
                                                pr_number=pr_number
                                            )
                                        )
                                else:
                                    print(f"PR creation failed: {pr_result.error}")
                            except Exception as e:
                                print(f"PR creation error: {e}")
                                import traceback
                                traceback.print_exc()
                    else:
                        print(f"Push failed: {push_result}")
                except Exception as e:
                    print(f"Git push error: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Step 8: Generate final report
            self._report_progress("running", 95, "Generating analysis report...")
            
            end_time = datetime.now()
            total_time = (end_time - start_time).total_seconds()
            summary.total_time = total_time
            
            # Print final summary
            self._print_final_summary(summary)
            
            # Count fixed vs failed
            fixed_count = sum(1 for f in all_fixes if f.status == FixStatus.FIXED)
            
            # Total issues = sandbox errors (initial) - counted by initial_errors
            # Note: code_review_issues may overlap, so we don't double count
            
            # Create result
            result = AnalysisResult(
                repo_url=request.repo_url,
                team_name=request.team_name,
                team_leader_name=request.team_leader_name,
                branch_name=branch_name,
                total_failures_detected=summary.initial_errors,
                total_fixes_applied=fixed_count,
                total_time_taken=total_time,
                fixes=all_fixes,
                test_results=test_results,
                generated_tests=generated_tests,
                commit_sha=commit_sha,
                branch_url=branch_url,
                commit_message=commit_message,
                start_time=start_time,
                end_time=end_time,
                status="completed",
                summary=summary.to_dict(),
                pr_url=pr_url,
                pr_number=pr_number,
                ci_status=ci_status,
                merged=False
            )
            
            self._report_progress("completed", 100, "Analysis complete!")
            
            return {"result": result, "summary": summary.to_dict()}
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._create_error_result(
                request, branch_name, start_time, 
                str(e)
            )
        finally:
            # Cleanup - remove cloned repo
            if repo_path and os.path.exists(repo_path):
                try:
                    await asyncio.sleep(0.5)
                    shutil.rmtree(repo_path, ignore_errors=True)
                except Exception as e:
                    print(f"Cleanup warning: {str(e)}")
    
    def _print_final_summary(self, summary: AnalysisSummary):
        """Print a comprehensive final summary to console"""
        print(f"\n{'='*60}")
        print(f"FINAL ANALYSIS SUMMARY")
        print(f"{'='*60}")
        print(f"Initial Errors:     {summary.initial_errors}")
        print(f"Final Errors:       {summary.final_errors}")
        print(f"Errors Resolved:    {summary.initial_errors - summary.final_errors}")
        print(f"Resolution Status:  {summary.resolution_status}")
        print(f"")
        print(f"Total Iterations:   {summary.total_iterations}")
        print(f"Fixes Attempted:    {summary.total_fixes_attempted}")
        print(f"Fixes Successful:   {summary.total_fixes_successful}")
        print(f"Total Time:         {summary.total_time:.2f}s")
        print(f"")
        
        if summary.iterations:
            print(f"ITERATION BREAKDOWN:")
            for it in summary.iterations:
                status = "✓" if it.errors_after < it.errors_before else "⚠"
                print(f"  {status} Iteration {it.iteration}: {it.errors_before}→{it.errors_after} errors, "
                      f"{it.fixes_successful}/{it.fixes_attempted} fixes, {it.time_taken:.2f}s")
        
        if summary.all_errors_found:
            print(f"\nALL ERRORS FOUND:")
            for err in summary.all_errors_found:
                status = "✓ Fixed" if summary.final_errors == 0 else "?"
                print(f"  - [{err['type']}] {err['file']}:{err['line']} - {status}")
        
        print(f"{'='*60}\n")
    
    async def _clone_repository(self, repo_url: str) -> str:
        """Clone a git repository"""
        try:
            # Generate unique directory name
            repo_name = repo_url.split('/')[-1].replace('.git', '')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            repo_path = os.path.join(settings.TEMP_REPO_DIR, f"{repo_name}_{timestamp}")
            
            # Ensure clean state
            if os.path.exists(repo_path):
                shutil.rmtree(repo_path)
            
            print(f"Cloning {repo_url} to {repo_path}...")
            
            # Clone repository
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, 
                lambda: Repo.clone_from(repo_url, repo_path, depth=1)
            )
            
            print(f"Clone successful. Listing files...")
            
            # List files for debugging
            for root, dirs, files in os.walk(repo_path):
                for f in files:
                    rel_path = os.path.relpath(os.path.join(root, f), repo_path)
                    print(f"  - {rel_path}")
                # Only show first level
                break
            
            return repo_path
            
        except Exception as e:
            print(f"Error cloning repository: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _create_error_result(self, request: AnalysisRequest, branch_name: str, 
                            start_time: datetime, error_message: str) -> Dict[str, Any]:
        """Create an error result"""
        end_time = datetime.now()
        
        result = AnalysisResult(
            repo_url=request.repo_url,
            team_name=request.team_name,
            team_leader_name=request.team_leader_name,
            branch_name=branch_name,
            total_failures_detected=0,
            total_fixes_applied=0,
            total_time_taken=(end_time - start_time).total_seconds(),
            fixes=[],
            test_results=[],
            generated_tests=[],
            commit_sha=None,
            branch_url=None,
            commit_message=None,
            start_time=start_time,
            end_time=end_time,
            status=f"error: {error_message}",
            pr_url=None,
            pr_number=None,
            ci_status=None,
            merged=False
        )
        
        self._report_progress("error", 0, error_message)
        
        return {"result": result, "error": error_message}
