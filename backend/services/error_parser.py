"""
Error Parser Service

Phase 4: Parse test output into structured bug data
Phase 5: Classify bugs into allowed categories (DETERMINISTIC - no LLM)

Bug Categories (per problem statement):
- SYNTAX: SyntaxError
- INDENTATION: IndentationError
- IMPORT: ImportError, ModuleNotFoundError
- LOGIC: NameError, TypeError, ValueError, AssertionError
- LINTING: flake8, pylint warnings
- TYPE_ERROR: mypy errors
"""

import re
from typing import List, Optional
from dataclasses import dataclass, field
from enum import Enum


class BugType(str, Enum):
    """Allowed bug categories per problem statement."""
    SYNTAX = "SYNTAX"
    INDENTATION = "INDENTATION"
    IMPORT = "IMPORT"
    LOGIC = "LOGIC"
    LINTING = "LINTING"
    TYPE_ERROR = "TYPE_ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass
class ParsedError:
    """Structured representation of a parsed error."""
    file: str
    line: int
    raw_error: str
    bug_type: BugType
    message: str
    context: str = ""  # Surrounding code context
    column: Optional[int] = None
    
    def to_display_format(self, fix_description: str = "") -> str:
        """
        Format error for dashboard display.
        
        Required format:
        SYNTAX error in src/validator.py line 8 → Fix: add colon
        """
        fix_part = f" → Fix: {fix_description}" if fix_description else ""
        return f"{self.bug_type.value} error in {self.file} line {self.line}{fix_part}"
    
    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "raw_error": self.raw_error,
            "bug_type": self.bug_type.value,
            "message": self.message,
            "column": self.column
        }


class ErrorParser:
    """
    Service for parsing test output and classifying bugs.
    
    Uses DETERMINISTIC mapping (NOT LLM) per problem statement:
    "Classification must be rule-based, not LLM-based"
    """
    
    # Error type to bug category mapping (deterministic)
    ERROR_CLASSIFICATION = {
        # Syntax errors
        "SyntaxError": BugType.SYNTAX,
        "invalid syntax": BugType.SYNTAX,
        
        # Indentation errors
        "IndentationError": BugType.INDENTATION,
        "unexpected indent": BugType.INDENTATION,
        "expected an indented block": BugType.INDENTATION,
        "unindent does not match": BugType.INDENTATION,
        
        # Import errors
        "ImportError": BugType.IMPORT,
        "ModuleNotFoundError": BugType.IMPORT,
        "No module named": BugType.IMPORT,
        "cannot import name": BugType.IMPORT,
        
        # Logic errors
        "NameError": BugType.LOGIC,
        "TypeError": BugType.LOGIC,
        "ValueError": BugType.LOGIC,
        "AttributeError": BugType.LOGIC,
        "KeyError": BugType.LOGIC,
        "IndexError": BugType.LOGIC,
        "AssertionError": BugType.LOGIC,
        "ZeroDivisionError": BugType.LOGIC,
        
        # Linting errors
        "flake8": BugType.LINTING,
        "pylint": BugType.LINTING,
        "E501": BugType.LINTING,  # flake8 line too long
        "E302": BugType.LINTING,  # flake8 expected 2 blank lines
        "W503": BugType.LINTING,  # flake8 line break before binary operator
        
        # Type errors (mypy)
        "mypy": BugType.TYPE_ERROR,
        "Incompatible types": BugType.TYPE_ERROR,
        "has no attribute": BugType.TYPE_ERROR,
        "Argument": BugType.TYPE_ERROR,
    }
    
    # Regex patterns for extracting file and line info
    PATTERNS = {
        # Python traceback: File "path/file.py", line 15
        "python_traceback": re.compile(
            r'File ["\'](.+?)["\'],\s*line\s*(\d+)',
            re.IGNORECASE
        ),
        # Pytest short format: path/file.py:15: ErrorType
        "pytest_short": re.compile(
            r'^(.+?\.py):(\d+):\s*(\w+Error)',
            re.MULTILINE
        ),
        # Node.js: at file.js:15:10
        "node_trace": re.compile(
            r'at\s+(?:.+?\s+\()?(.+?\.(?:js|ts|jsx|tsx)):(\d+):?(\d+)?',
            re.IGNORECASE
        ),
        # Jest/Mocha: file.test.js:15
        "jest": re.compile(
            r'(.+?\.(?:test|spec)\.(?:js|ts|jsx|tsx)):(\d+)',
            re.IGNORECASE
        ),
        # ESLint: path/file.js:15:10 error message
        "eslint": re.compile(
            r'^(.+?\.(?:js|ts|jsx|tsx)):(\d+):(\d+)\s+(error|warning)',
            re.MULTILINE | re.IGNORECASE
        ),
        # Generic: file:line pattern
        "generic": re.compile(
            r'([^\s:]+\.(?:py|js|ts|jsx|tsx)):(\d+)',
            re.IGNORECASE
        ),
    }
    
    def classify_error(self, error_text: str) -> BugType:
        """
        Classify error into bug category using DETERMINISTIC mapping.
        
        Per problem statement:
        "⚠ Must NOT use LLM here. Reason: Judges test exact classification."
        """
        # Check each pattern in order of specificity
        for pattern, bug_type in self.ERROR_CLASSIFICATION.items():
            if pattern.lower() in error_text.lower():
                return bug_type
        
        return BugType.UNKNOWN
    
    def extract_error_message(self, error_text: str) -> str:
        """Extract the core error message from error text."""
        # Try to find error type and message
        patterns = [
            r'(\w+Error):\s*(.+?)(?:\n|$)',
            r'(Error):\s*(.+?)(?:\n|$)',
            r'(error):\s*(.+?)(?:\n|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, error_text, re.IGNORECASE)
            if match:
                return f"{match.group(1)}: {match.group(2).strip()}"
        
        # Return first non-empty line
        lines = [l.strip() for l in error_text.split('\n') if l.strip()]
        return lines[0] if lines else error_text[:100]
    
    def parse_python_output(self, output: str) -> List[ParsedError]:
        """Parse Python test output (pytest, unittest)."""
        errors = []
        seen = set()  # Deduplicate errors
        
        # Find all file:line references
        for match in self.PATTERNS["python_traceback"].finditer(output):
            file_path = match.group(1)
            line_num = int(match.group(2))
            
            # Skip test framework internals
            if any(skip in file_path for skip in [
                "site-packages", "pytest", "unittest", "_pytest",
                "python3", "lib/python"
            ]):
                continue
            
            # Normalize file path
            file_path = file_path.replace("\\", "/")
            if file_path.startswith("/app/"):
                file_path = file_path[5:]  # Remove Docker mount prefix
            
            key = (file_path, line_num)
            if key in seen:
                continue
            seen.add(key)
            
            # Extract surrounding context for error classification
            start = max(0, match.start() - 200)
            end = min(len(output), match.end() + 500)
            context = output[start:end]
            
            # Classify the error
            bug_type = self.classify_error(context)
            message = self.extract_error_message(context)
            
            # Extract raw error type
            raw_error_match = re.search(r'(\w+Error|\w+Exception)', context)
            raw_error = raw_error_match.group(1) if raw_error_match else "Error"
            
            errors.append(ParsedError(
                file=file_path,
                line=line_num,
                raw_error=raw_error,
                bug_type=bug_type,
                message=message,
                context=context
            ))
        
        # Also check pytest short format
        for match in self.PATTERNS["pytest_short"].finditer(output):
            file_path = match.group(1).replace("\\", "/")
            if file_path.startswith("/app/"):
                file_path = file_path[5:]
            line_num = int(match.group(2))
            error_type = match.group(3)
            
            key = (file_path, line_num)
            if key in seen:
                continue
            seen.add(key)
            
            bug_type = self.classify_error(error_type)
            
            errors.append(ParsedError(
                file=file_path,
                line=line_num,
                raw_error=error_type,
                bug_type=bug_type,
                message=error_type
            ))
        
        return errors
    
    def parse_node_output(self, output: str) -> List[ParsedError]:
        """Parse Node.js test output (Jest, Mocha, npm test)."""
        errors = []
        seen = set()
        
        # Check Jest/Mocha patterns
        for pattern_name in ["node_trace", "jest", "eslint", "generic"]:
            pattern = self.PATTERNS[pattern_name]
            for match in pattern.finditer(output):
                file_path = match.group(1).replace("\\", "/")
                if file_path.startswith("/app/"):
                    file_path = file_path[5:]
                
                # Skip node_modules
                if "node_modules" in file_path:
                    continue
                
                line_num = int(match.group(2))
                
                key = (file_path, line_num)
                if key in seen:
                    continue
                seen.add(key)
                
                # Extract context
                start = max(0, match.start() - 200)
                end = min(len(output), match.end() + 500)
                context = output[start:end]
                
                bug_type = self.classify_error(context)
                message = self.extract_error_message(context)
                
                errors.append(ParsedError(
                    file=file_path,
                    line=line_num,
                    raw_error="Error",
                    bug_type=bug_type,
                    message=message,
                    context=context
                ))
        
        return errors
    
    def parse_output(self, stdout: str, stderr: str, project_type: str) -> List[ParsedError]:
        """
        Parse test output and return structured errors.
        
        Args:
            stdout: Standard output from test execution
            stderr: Standard error from test execution
            project_type: "python" or "node"
            
        Returns:
            List of ParsedError objects
        """
        combined = f"{stdout}\n{stderr}"
        
        if project_type == "python":
            return self.parse_python_output(combined)
        elif project_type == "node":
            return self.parse_node_output(combined)
        else:
            # Try both parsers
            errors = self.parse_python_output(combined)
            if not errors:
                errors = self.parse_node_output(combined)
            return errors
    
    def get_primary_error(self, errors: List[ParsedError]) -> Optional[ParsedError]:
        """
        Get the most important error to fix first.
        
        Priority:
        1. SYNTAX (can't run without fixing)
        2. INDENTATION
        3. IMPORT
        4. TYPE_ERROR
        5. LOGIC
        6. LINTING
        """
        priority_order = [
            BugType.SYNTAX,
            BugType.INDENTATION,
            BugType.IMPORT,
            BugType.TYPE_ERROR,
            BugType.LOGIC,
            BugType.LINTING,
            BugType.UNKNOWN
        ]
        
        for bug_type in priority_order:
            for error in errors:
                if error.bug_type == bug_type:
                    return error
        
        return errors[0] if errors else None


# Singleton instance
error_parser = ErrorParser()
