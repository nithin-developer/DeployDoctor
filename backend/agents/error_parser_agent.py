"""
Error Parser Agent - Parses and classifies errors from execution output.

This agent is responsible for:
1. Parsing stdout/stderr from test execution
2. Extracting file paths, line numbers, error messages
3. Classifying bugs by type (SYNTAX, IMPORT, LOGIC, etc.)
"""

import re
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from agents.base_agent import BaseAgent, AgentResult, AgentStatus


class BugType(str, Enum):
    """Classification of bug types."""
    SYNTAX = "SYNTAX"
    INDENTATION = "INDENTATION"  
    IMPORT = "IMPORT"
    LOGIC = "LOGIC"
    LINTING = "LINTING"
    TYPE_ERROR = "TYPE_ERROR"
    RUNTIME = "RUNTIME"
    TEST_FAILURE = "TEST_FAILURE"
    UNKNOWN = "UNKNOWN"


@dataclass
class ParsedError:
    """A parsed error from execution output."""
    file_path: str
    line_number: int
    message: str
    error_type: str
    bug_type: BugType
    code_snippet: Optional[str] = None
    column: Optional[int] = None
    
    def to_dict(self) -> Dict:
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "message": self.message,
            "error_type": self.error_type,
            "bug_type": self.bug_type.value,
            "code_snippet": self.code_snippet,
            "column": self.column
        }


class ErrorParserAgent(BaseAgent):
    """
    Agent responsible for parsing and classifying errors.
    
    Uses deterministic rules (NOT LLM) per problem statement requirements.
    Supports Python and Node.js error formats.
    """
    
    # Error type to bug type mapping (deterministic)
    BUG_TYPE_MAPPING = {
        # Python errors
        "SyntaxError": BugType.SYNTAX,
        "IndentationError": BugType.INDENTATION,
        "TabError": BugType.INDENTATION,
        "ImportError": BugType.IMPORT,
        "ModuleNotFoundError": BugType.IMPORT,
        "TypeError": BugType.TYPE_ERROR,
        "AttributeError": BugType.TYPE_ERROR,
        "NameError": BugType.LOGIC,
        "ValueError": BugType.LOGIC,
        "KeyError": BugType.LOGIC,
        "IndexError": BugType.LOGIC,
        "RuntimeError": BugType.RUNTIME,
        "AssertionError": BugType.TEST_FAILURE,
        "ZeroDivisionError": BugType.LOGIC,
        "FileNotFoundError": BugType.LOGIC,
        "PermissionError": BugType.RUNTIME,
        "RecursionError": BugType.LOGIC,
        "StopIteration": BugType.LOGIC,
        "UnboundLocalError": BugType.LOGIC,
        
        # Node.js/JavaScript errors
        "ReferenceError": BugType.LOGIC,
        "SyntaxError": BugType.SYNTAX,
        "RangeError": BugType.LOGIC,
        "EvalError": BugType.RUNTIME,
        "URIError": BugType.LOGIC,
        "Error": BugType.RUNTIME,
        
        # Linting
        "E501": BugType.LINTING,  # Line too long
        "W503": BugType.LINTING,  # Line break before operator
        "E302": BugType.LINTING,  # Expected 2 blank lines
        "E303": BugType.LINTING,  # Too many blank lines
        "F401": BugType.LINTING,  # Imported but unused
        "F841": BugType.LINTING,  # Local variable never used
    }
    
    # Regex patterns for different error formats
    PATTERNS = {
        # Python traceback: File "path", line N
        "python_traceback": re.compile(
            r'File "([^"]+)", line (\d+)(?:, in \w+)?\s*\n\s*(.*?)\n(\s*\^+)?\s*\n?(\w+Error|\w+Exception): (.+)',
            re.MULTILINE | re.DOTALL
        ),
        
        # Python simple error: path:line: ErrorType: message
        "python_simple": re.compile(
            r'^([^\s:]+\.py):(\d+):(?:\d+:)?\s*(\w+(?:Error|Exception|Warning)?):\s*(.+)$',
            re.MULTILINE
        ),
        
        # Pytest failure
        "pytest_failure": re.compile(
            r'FAILED\s+([^\s]+)::([^\s]+)\s+-\s+(.+)',
            re.MULTILINE
        ),
        
        # Pytest assertion error
        "pytest_assert": re.compile(
            r'([^\s]+\.py):(\d+):\s*(AssertionError|assert\s+.+)',
            re.MULTILINE
        ),
        
        # Node.js error with stack trace
        "node_error": re.compile(
            r'(\w+Error): (.+?)\n\s+at .+?\(([^\s:]+):(\d+):(\d+)\)',
            re.MULTILINE
        ),
        
        # ESLint/TSLint format: path:line:col: message
        "eslint": re.compile(
            r'^([^\s:]+\.[jt]sx?):(\d+):(\d+):\s*(error|warning)\s+(.+?)(?:\s+(\S+))?$',
            re.MULTILINE
        ),
        
        # Generic error with file:line
        "generic": re.compile(
            r'^([^\s:]+):(\d+):(?:\d+:)?\s*(.+)$',
            re.MULTILINE
        ),
    }
    
    def __init__(self):
        super().__init__(
            name="Error Parser Agent",
            description="I parse error output and classify bugs using deterministic rules.",
            use_llm=False  # Uses deterministic rules, not LLM
        )
    
    def classify_error(self, error_type: str) -> BugType:
        """
        Classify an error type to a BugType.
        
        Uses deterministic mapping per problem statement requirements.
        """
        # Direct lookup
        if error_type in self.BUG_TYPE_MAPPING:
            return self.BUG_TYPE_MAPPING[error_type]
        
        # Check if error type contains known types
        error_lower = error_type.lower()
        
        if 'syntax' in error_lower:
            return BugType.SYNTAX
        if 'indent' in error_lower or 'tab' in error_lower:
            return BugType.INDENTATION
        if 'import' in error_lower or 'module' in error_lower:
            return BugType.IMPORT
        if 'type' in error_lower or 'attribute' in error_lower:
            return BugType.TYPE_ERROR
        if 'assert' in error_lower:
            return BugType.TEST_FAILURE
        if any(c in error_lower for c in ['name', 'key', 'index', 'value', 'reference']):
            return BugType.LOGIC
        if 'runtime' in error_lower:
            return BugType.RUNTIME
        if error_type.startswith(('E', 'W', 'F', 'C', 'N')):
            return BugType.LINTING
        
        return BugType.UNKNOWN
    
    def parse_python_output(self, output: str) -> List[ParsedError]:
        """Parse Python error output."""
        errors = []
        seen = set()  # Avoid duplicates
        
        # Try Python traceback pattern
        for match in self.PATTERNS["python_traceback"].finditer(output):
            file_path = match.group(1)
            line_num = int(match.group(2))
            code_snippet = match.group(3).strip()
            error_type = match.group(5)
            message = match.group(6).strip()
            
            key = (file_path, line_num, error_type)
            if key not in seen:
                seen.add(key)
                errors.append(ParsedError(
                    file_path=file_path,
                    line_number=line_num,
                    message=message,
                    error_type=error_type,
                    bug_type=self.classify_error(error_type),
                    code_snippet=code_snippet
                ))
        
        # Try simple Python error pattern
        for match in self.PATTERNS["python_simple"].finditer(output):
            file_path = match.group(1)
            line_num = int(match.group(2))
            error_type = match.group(3)
            message = match.group(4).strip()
            
            key = (file_path, line_num, error_type)
            if key not in seen:
                seen.add(key)
                errors.append(ParsedError(
                    file_path=file_path,
                    line_number=line_num,
                    message=message,
                    error_type=error_type,
                    bug_type=self.classify_error(error_type)
                ))
        
        # Try pytest patterns
        for match in self.PATTERNS["pytest_assert"].finditer(output):
            file_path = match.group(1)
            line_num = int(match.group(2))
            message = match.group(3).strip()
            
            key = (file_path, line_num, "AssertionError")
            if key not in seen:
                seen.add(key)
                errors.append(ParsedError(
                    file_path=file_path,
                    line_number=line_num,
                    message=message,
                    error_type="AssertionError",
                    bug_type=BugType.TEST_FAILURE
                ))
        
        return errors
    
    def parse_node_output(self, output: str) -> List[ParsedError]:
        """Parse Node.js error output."""
        errors = []
        seen = set()
        
        # Try Node error pattern
        for match in self.PATTERNS["node_error"].finditer(output):
            error_type = match.group(1)
            message = match.group(2).strip()
            file_path = match.group(3)
            line_num = int(match.group(4))
            column = int(match.group(5))
            
            key = (file_path, line_num, error_type)
            if key not in seen:
                seen.add(key)
                errors.append(ParsedError(
                    file_path=file_path,
                    line_number=line_num,
                    message=message,
                    error_type=error_type,
                    bug_type=self.classify_error(error_type),
                    column=column
                ))
        
        # Try ESLint pattern
        for match in self.PATTERNS["eslint"].finditer(output):
            file_path = match.group(1)
            line_num = int(match.group(2))
            column = int(match.group(3))
            severity = match.group(4)
            message = match.group(5).strip()
            rule = match.group(6) if match.group(6) else ""
            
            error_type = rule if rule else f"eslint-{severity}"
            
            key = (file_path, line_num, error_type)
            if key not in seen:
                seen.add(key)
                errors.append(ParsedError(
                    file_path=file_path,
                    line_number=line_num,
                    message=message,
                    error_type=error_type,
                    bug_type=BugType.LINTING,
                    column=column
                ))
        
        return errors
    
    def parse_generic_output(self, output: str) -> List[ParsedError]:
        """Parse generic error output."""
        errors = []
        seen = set()
        
        for match in self.PATTERNS["generic"].finditer(output):
            file_path = match.group(1)
            line_num = int(match.group(2))
            message = match.group(3).strip()
            
            # Skip if looks like a path or timestamp
            if '/' not in file_path and '\\' not in file_path:
                if not file_path.endswith(('.py', '.js', '.ts', '.jsx', '.tsx')):
                    continue
            
            key = (file_path, line_num, message[:50])
            if key not in seen:
                seen.add(key)
                errors.append(ParsedError(
                    file_path=file_path,
                    line_number=line_num,
                    message=message,
                    error_type="Error",
                    bug_type=BugType.UNKNOWN
                ))
        
        return errors
    
    def parse_output(
        self, 
        output: str, 
        project_type: str = "unknown"
    ) -> List[ParsedError]:
        """
        Parse error output and return list of parsed errors.
        
        Args:
            output: Combined stdout/stderr from execution
            project_type: 'python', 'node', or 'unknown'
            
        Returns:
            List of ParsedError objects
        """
        errors = []
        
        if project_type == 'python' or project_type == 'unknown':
            errors.extend(self.parse_python_output(output))
        
        if project_type == 'node' or project_type == 'unknown':
            errors.extend(self.parse_node_output(output))
        
        # Try generic if we still don't have errors
        if not errors:
            errors.extend(self.parse_generic_output(output))
        
        # Sort by file and line number
        errors.sort(key=lambda e: (e.file_path, e.line_number))
        
        # Deduplicate
        unique_errors = []
        seen = set()
        for error in errors:
            key = (error.file_path, error.line_number, error.error_type)
            if key not in seen:
                seen.add(key)
                unique_errors.append(error)
        
        return unique_errors
    
    def get_highest_priority_error(self, errors: List[ParsedError]) -> Optional[ParsedError]:
        """
        Get the highest priority error to fix first.
        
        Priority order:
        1. SYNTAX - Code won't run
        2. INDENTATION - Python-specific syntax
        3. IMPORT - Missing dependencies
        4. TYPE_ERROR - Type mismatches
        5. LOGIC - Runtime issues
        6. TEST_FAILURE - Test assertions
        7. LINTING - Style issues
        8. UNKNOWN - Others
        """
        priority_order = [
            BugType.SYNTAX,
            BugType.INDENTATION,
            BugType.IMPORT,
            BugType.TYPE_ERROR,
            BugType.LOGIC,
            BugType.TEST_FAILURE,
            BugType.RUNTIME,
            BugType.LINTING,
            BugType.UNKNOWN
        ]
        
        for bug_type in priority_order:
            for error in errors:
                if error.bug_type == bug_type:
                    return error
        
        return errors[0] if errors else None
    
    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        Parse errors from execution output.
        
        Context should contain:
            - output: Combined stdout/stderr
            - project_type: 'python', 'node', or 'unknown'
            - execution_results: (optional) List of ExecutionResult dicts
        """
        start_time = time.time()
        
        output = context.get("output", "")
        project_type = context.get("project_type", "unknown")
        execution_results = context.get("execution_results", [])
        
        # Combine all outputs
        if execution_results:
            all_output = []
            for result in execution_results:
                if isinstance(result, dict):
                    all_output.append(result.get("stdout", ""))
                    all_output.append(result.get("stderr", ""))
            output = "\n".join(all_output)
        
        if not output:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                data={
                    "errors": [],
                    "total_errors": 0,
                    "message": "No output to parse"
                },
                duration_seconds=time.time() - start_time
            )
        
        # Parse errors
        errors = self.parse_output(output, project_type)
        
        # Get highest priority
        priority_error = self.get_highest_priority_error(errors)
        
        # Count by type
        error_counts = {}
        for error in errors:
            bug_type = error.bug_type.value
            error_counts[bug_type] = error_counts.get(bug_type, 0) + 1
        
        duration = time.time() - start_time
        
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            data={
                "errors": [e.to_dict() for e in errors],
                "total_errors": len(errors),
                "error_counts_by_type": error_counts,
                "highest_priority": priority_error.to_dict() if priority_error else None
            },
            duration_seconds=duration
        )
