"""
Code Fixer Agent - Uses LLM to generate code fixes.

This agent is responsible for:
1. Analyzing code errors
2. Generating minimal fixes using Groq LLM
3. Applying fixes to files
4. Validating fixed code
"""

import os
import re
import json
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage

from agents.base_agent import BaseAgent, AgentResult, AgentStatus
from agents.error_parser_agent import ParsedError, BugType


@dataclass
class CodeFix:
    """A code fix to be applied."""
    file_path: str
    line_number: int
    bug_type: str
    original_code: str
    fixed_code: str
    explanation: str
    confidence: float = 0.0
    success: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "bug_type": self.bug_type,
            "original_code": self.original_code,
            "fixed_code": self.fixed_code,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "success": self.success
        }


class CodeFixerAgent(BaseAgent):
    """
    Agent responsible for fixing code using LLM.
    
    Uses Groq LLM to analyze errors and generate minimal fixes.
    Follows constraints:
    - Minimal changes only
    - No refactoring
    - Preserve code style
    """
    
    SYSTEM_PROMPT = """You are an expert code fixer. Your job is to fix code errors with MINIMAL changes.

IMPORTANT RULES:
1. Make the SMALLEST possible fix to resolve the error
2. DO NOT refactor or improve code beyond the fix
3. DO NOT add new features or optimizations
4. Preserve the original code style and formatting
5. Only fix the specific error mentioned
6. Return ONLY valid JSON with the fix

You will receive:
- The file content
- The error message
- The error line number
- The bug type

Respond with ONLY a JSON object in this exact format:
{
    "original_code": "the exact lines that need to change",
    "fixed_code": "the corrected version of those lines",
    "explanation": "brief explanation of what was fixed",
    "confidence": 0.95
}

Make sure:
- original_code contains enough context to be unique in the file
- fixed_code is the corrected version
- Do not include markdown code blocks, just raw JSON"""

    def __init__(self):
        super().__init__(
            name="Code Fixer Agent",
            description="I analyze code errors and generate minimal fixes using AI.",
            use_llm=True
        )
    
    def _extract_json(self, text: str) -> Optional[Dict]:
        """Extract JSON from LLM response."""
        # Try to parse directly
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON in markdown code blocks
        code_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find first JSON object
        start = text.find('{')
        if start == -1:
            return None
        
        # Find matching closing brace
        depth = 0
        in_string = False
        escape_next = False
        
        for i in range(start, len(text)):
            char = text[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            
            if in_string:
                continue
            
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i+1])
                    except json.JSONDecodeError:
                        pass
                    break
        
        return None
    
    def _get_code_context(
        self, 
        file_content: str, 
        error_line: int, 
        context_lines: int = 5
    ) -> str:
        """Get code context around the error line."""
        lines = file_content.split('\n')
        
        start = max(0, error_line - context_lines - 1)
        end = min(len(lines), error_line + context_lines)
        
        context_with_numbers = []
        for i in range(start, end):
            line_num = i + 1
            marker = " >>> " if line_num == error_line else "     "
            context_with_numbers.append(f"{line_num:4d}{marker}{lines[i]}")
        
        return '\n'.join(context_with_numbers)
    
    def _build_fix_prompt(
        self,
        file_path: str,
        file_content: str,
        error_message: str,
        error_line: int,
        bug_type: str
    ) -> str:
        """Build the prompt for fix generation."""
        context = self._get_code_context(file_content, error_line)
        
        return f"""Fix the following error:

FILE: {file_path}
ERROR LINE: {error_line}
BUG TYPE: {bug_type}
ERROR MESSAGE: {error_message}

CODE CONTEXT (error line marked with >>>):
{context}

FULL FILE:
```
{file_content}
```

Generate a minimal fix for this error. Return ONLY a JSON object with:
- original_code: the exact code that needs to change
- fixed_code: the corrected code
- explanation: brief description of the fix
- confidence: your confidence level (0.0 to 1.0)"""

    async def generate_fix(
        self,
        file_path: str,
        file_content: str,
        error_message: str,
        error_line: int,
        bug_type: str
    ) -> Optional[CodeFix]:
        """
        Generate a fix for a code error using LLM.
        
        Args:
            file_path: Path to the file
            file_content: Current content of the file
            error_message: The error message
            error_line: Line number where error occurs
            bug_type: Type of bug (SYNTAX, IMPORT, etc.)
            
        Returns:
            CodeFix object or None if fix generation failed
        """
        # Validate error_line
        if error_line is None:
            error_line = 1
        
        prompt = self._build_fix_prompt(
            file_path, file_content, error_message, error_line, bug_type
        )
        
        try:
            response = await self.invoke_llm(self.SYSTEM_PROMPT, prompt)
            
            fix_data = self._extract_json(response)
            
            if not fix_data:
                return None
            
            return CodeFix(
                file_path=file_path,
                line_number=error_line,
                bug_type=bug_type,
                original_code=fix_data.get("original_code", ""),
                fixed_code=fix_data.get("fixed_code", ""),
                explanation=fix_data.get("explanation", ""),
                confidence=float(fix_data.get("confidence", 0.5))
            )
            
        except Exception as e:
            print(f"Error generating fix: {e}")
            return None
    
    def apply_fix(self, file_content: str, fix: CodeFix) -> Optional[str]:
        """
        Apply a fix to file content.
        
        Args:
            file_content: Current file content
            fix: CodeFix to apply
            
        Returns:
            Updated file content or None if fix couldn't be applied
        """
        if not fix.fixed_code:
            return None
        
        # Validate line_number is not None
        if fix.line_number is None:
            return None
        
        lines = file_content.split('\n')
        error_idx = fix.line_number - 1
        
        # Validate line number
        if error_idx < 0 or error_idx >= len(lines):
            return None
        
        original_line = lines[error_idx]
        original_trimmed = fix.original_code.strip() if fix.original_code else ""
        fixed_trimmed = fix.fixed_code.strip()
        
        # Check if original_code spans multiple lines
        original_parts = original_trimmed.split('\n') if original_trimmed else []
        fixed_parts = fixed_trimmed.split('\n')
        
        # Get base indentation from error line
        indentation = original_line[:len(original_line) - len(original_line.lstrip())]
        
        # Handle multi-line originals (LLM gave context of multiple broken lines)
        if len(original_parts) > 1:
            # Number of lines to remove starting from error_idx
            lines_to_remove = len(original_parts)
            end_idx = min(error_idx + lines_to_remove, len(lines))
            
            # Apply proper indentation to fixed lines
            new_lines = []
            for i, fixed_line in enumerate(fixed_parts):
                stripped = fixed_line.strip()
                if i == 0:
                    new_lines.append(indentation + stripped)
                else:
                    # Try to preserve relative indentation from fixed code
                    leading = len(fixed_line) - len(fixed_line.lstrip())
                    rel_indent = '    ' * (leading // 4)  # Convert to 4-space indents
                    new_lines.append(indentation + rel_indent + stripped)
            
            # Replace the original lines with fixed lines
            lines = lines[:error_idx] + new_lines + lines[end_idx:]
            fix.success = True
            return '\n'.join(lines)
        
        # Single line original
        if original_trimmed and original_trimmed in original_line:
            # Replace just the matching part on this specific line
            new_line = original_line.replace(original_trimmed, fixed_trimmed, 1)
            lines[error_idx] = new_line
            fix.success = True
            return '\n'.join(lines)
        
        # Check if the trimmed line content matches
        if original_trimmed and original_line.strip() == original_trimmed:
            # Preserve indentation
            lines[error_idx] = indentation + fixed_trimmed
            fix.success = True
            return '\n'.join(lines)
        
        # Fallback: Replace single line with fixed code (multi-line fix)
        if len(fixed_parts) == 1:
            lines[error_idx] = indentation + fixed_trimmed
            fix.success = True
            return '\n'.join(lines)
        else:
            # Multi-line fix for single-line error
            new_lines = []
            for i, fixed_line in enumerate(fixed_parts):
                stripped = fixed_line.strip()
                if i == 0:
                    new_lines.append(indentation + stripped)
                else:
                    leading = len(fixed_line) - len(fixed_line.lstrip())
                    rel_indent = '    ' * (leading // 4)
                    new_lines.append(indentation + rel_indent + stripped)
            
            lines = lines[:error_idx] + new_lines + lines[error_idx + 1:]
            fix.success = True
            return '\n'.join(lines)
    
    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        Generate and optionally apply fixes for errors.
        
        Context should contain:
            - repo_path: Path to the repository
            - errors: List of ParsedError dicts or objects
            - apply_fixes: Whether to apply fixes to files (default: True)
            - max_fixes: Maximum number of fixes to generate (default: 5)
        """
        start_time = time.time()
        
        repo_path = context.get("repo_path")
        errors = context.get("errors", [])
        apply_fixes = context.get("apply_fixes", True)
        max_fixes = context.get("max_fixes", 5)
        
        if not repo_path:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                error="No repository path provided"
            )
        
        if not errors:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                data={
                    "fixes": [],
                    "total_fixes": 0,
                    "message": "No errors to fix"
                },
                duration_seconds=time.time() - start_time
            )
        
        repo_path = Path(repo_path)
        fixes_generated = []
        fixes_applied = []
        
        # Process errors (limited to max_fixes)
        errors_to_fix = errors[:max_fixes]
        
        for i, error in enumerate(errors_to_fix):
            # Handle both dict and object formats
            if isinstance(error, dict):
                file_path = error.get("file_path", error.get("file"))
                line_number = error.get("line_number", error.get("line")) or 1
                message = error.get("message", error.get("error_message", "Unknown error"))
                bug_type = error.get("bug_type", "UNKNOWN")
            else:
                file_path = getattr(error, "file_path", None)
                line_number = getattr(error, "line_number", None) or 1
                message = getattr(error, "message", "Unknown error")
                bug_type = getattr(error, "bug_type", BugType.UNKNOWN)
                if hasattr(bug_type, "value"):
                    bug_type = bug_type.value
            
            if not file_path:
                continue
            
            # Get full file path
            full_path = repo_path / file_path
            if not full_path.exists():
                # Try relative path from repo
                for p in repo_path.rglob(Path(file_path).name):
                    full_path = p
                    break
            
            if not full_path.exists():
                continue
            
            self.report_progress(
                "fixing", 
                int(20 + (60 * i / len(errors_to_fix))),
                f"Fixing {file_path}:{line_number}"
            )
            
            try:
                # Read file
                file_content = full_path.read_text(encoding='utf-8')
                
                # Generate fix
                fix = await self.generate_fix(
                    file_path=str(file_path),
                    file_content=file_content,
                    error_message=message,
                    error_line=line_number,
                    bug_type=bug_type
                )
                
                if fix:
                    fixes_generated.append(fix)
                    
                    # Apply fix if requested
                    if apply_fixes:
                        new_content = self.apply_fix(file_content, fix)
                        if new_content:
                            full_path.write_text(new_content, encoding='utf-8')
                            fix.success = True
                            fixes_applied.append(fix)
                    
            except Exception as e:
                print(f"Error fixing {file_path}: {e}")
                continue
        
        duration = time.time() - start_time
        
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS if fixes_applied else AgentStatus.FAILED,
            data={
                "fixes_generated": len(fixes_generated),
                "fixes_applied": len(fixes_applied),
                "fixes": [f.to_dict() for f in fixes_generated],
                "applied_fixes": [f.to_dict() for f in fixes_applied]
            },
            duration_seconds=duration
        )
