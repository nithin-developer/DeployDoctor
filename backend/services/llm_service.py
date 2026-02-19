"""
LLM Service for Fix Generation using Groq API

Phase 6: Generate minimal code corrections using LLM.

Requirements per problem statement:
- Minimal fix (no refactoring)
- Modify only necessary lines
- Avoid formatting unrelated code
- Return full corrected file
"""

import os
from typing import Optional
from dataclasses import dataclass

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from config.settings import get_settings
from services.error_parser import ParsedError, BugType

settings = get_settings()


@dataclass
class FixResult:
    """Result of LLM fix generation."""
    success: bool
    fixed_content: str
    fix_description: str
    error: Optional[str] = None
    lines_changed: int = 0


class LLMService:
    """
    Service for generating code fixes using Groq LLM.
    
    Uses LangChain with Groq for:
    - Fast inference
    - Cost-effective
    - High-quality fixes
    """
    
    # System prompt for minimal fix generation
    SYSTEM_PROMPT = """You are an expert code debugging assistant. Your task is to fix code errors with MINIMAL changes.

CRITICAL RULES:
1. ONLY fix the specific error mentioned - do not refactor or improve other code
2. Return the COMPLETE fixed file content - every single line
3. Make the SMALLEST possible change to fix the error
4. Do NOT add comments explaining the fix
5. Do NOT change formatting, whitespace, or style of other lines
6. Preserve ALL existing code that is not directly related to the fix
7. Do NOT add new features or optimizations

You will receive:
- The full file content
- The error type and line number
- The error message

Respond with ONLY the corrected file content. No explanations, no markdown, no code blocks - just the raw fixed code."""

    FIX_PROMPT_TEMPLATE = """Fix the following {bug_type} error in this file.

ERROR DETAILS:
- Bug Type: {bug_type}
- File: {file_path}
- Line: {line_number}
- Error: {error_message}

CURRENT FILE CONTENT:
```
{file_content}
```

Return ONLY the complete fixed file content. No explanations, no markdown code blocks."""

    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.model = settings.GROQ_MODEL
        self._llm = None
    
    @property
    def llm(self) -> ChatGroq:
        """Lazy initialization of LLM client."""
        if self._llm is None:
            if not self.api_key:
                raise ValueError("GROQ_API_KEY is not set in environment variables")
            
            self._llm = ChatGroq(
                api_key=self.api_key,
                model=self.model,
                temperature=0,  # Deterministic output for consistent fixes
                max_tokens=8192,
            )
        return self._llm
    
    def _read_file(self, file_path: str) -> str:
        """Read file content."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _write_file(self, file_path: str, content: str) -> None:
        """Write content to file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _count_changed_lines(self, original: str, fixed: str) -> int:
        """Count number of lines that changed."""
        original_lines = original.splitlines()
        fixed_lines = fixed.splitlines()
        
        changes = 0
        max_len = max(len(original_lines), len(fixed_lines))
        
        for i in range(max_len):
            orig = original_lines[i] if i < len(original_lines) else ""
            fix = fixed_lines[i] if i < len(fixed_lines) else ""
            if orig != fix:
                changes += 1
        
        return changes
    
    def _clean_llm_response(self, response: str) -> str:
        """
        Clean LLM response to extract just the code.
        Removes markdown code blocks if present.
        """
        content = response.strip()
        
        # Remove markdown code blocks
        if content.startswith("```"):
            # Find the end of the first line (language specifier)
            first_newline = content.find('\n')
            if first_newline != -1:
                content = content[first_newline + 1:]
            
            # Remove closing ```
            if content.endswith("```"):
                content = content[:-3]
            elif "```" in content:
                content = content[:content.rfind("```")]
        
        return content.strip()
    
    def _generate_fix_description(self, error: ParsedError) -> str:
        """
        Generate a short fix description for the dashboard.
        
        Format: "add colon", "fix indentation", "add import", etc.
        """
        descriptions = {
            BugType.SYNTAX: "fix syntax",
            BugType.INDENTATION: "fix indentation",
            BugType.IMPORT: "fix import",
            BugType.LOGIC: "fix logic error",
            BugType.TYPE_ERROR: "fix type error",
            BugType.LINTING: "fix linting error",
            BugType.UNKNOWN: "fix error",
        }
        return descriptions.get(error.bug_type, "fix error")
    
    def generate_fix(
        self,
        repo_dir: str,
        error: ParsedError
    ) -> FixResult:
        """
        Generate a fix for the given error.
        
        Args:
            repo_dir: Path to the repository
            error: ParsedError object with error details
            
        Returns:
            FixResult with fixed content and metadata
        """
        file_path = os.path.join(repo_dir, error.file)
        
        # Read current file content
        try:
            original_content = self._read_file(file_path)
        except FileNotFoundError:
            return FixResult(
                success=False,
                fixed_content="",
                fix_description="",
                error=f"File not found: {error.file}"
            )
        except Exception as e:
            return FixResult(
                success=False,
                fixed_content="",
                fix_description="",
                error=f"Error reading file: {str(e)}"
            )
        
        # Build the fix prompt
        prompt = self.FIX_PROMPT_TEMPLATE.format(
            bug_type=error.bug_type.value,
            file_path=error.file,
            line_number=error.line,
            error_message=error.message,
            file_content=original_content
        )
        
        try:
            # Call LLM
            messages = [
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ]
            
            response = self.llm.invoke(messages)
            fixed_content = self._clean_llm_response(response.content)
            
            # Validate response is not empty
            if not fixed_content.strip():
                return FixResult(
                    success=False,
                    fixed_content="",
                    fix_description="",
                    error="LLM returned empty response"
                )
            
            # Count changed lines
            lines_changed = self._count_changed_lines(original_content, fixed_content)
            
            # Generate fix description
            fix_description = self._generate_fix_description(error)
            
            return FixResult(
                success=True,
                fixed_content=fixed_content,
                fix_description=fix_description,
                lines_changed=lines_changed
            )
            
        except Exception as e:
            return FixResult(
                success=False,
                fixed_content="",
                fix_description="",
                error=f"LLM error: {str(e)}"
            )
    
    def apply_fix(self, repo_dir: str, error: ParsedError, fix_result: FixResult) -> bool:
        """
        Apply the fix to the file.
        
        Args:
            repo_dir: Path to the repository
            error: The error being fixed
            fix_result: The fix result from LLM
            
        Returns:
            True if fix was applied successfully
        """
        if not fix_result.success:
            return False
        
        file_path = os.path.join(repo_dir, error.file)
        
        try:
            self._write_file(file_path, fix_result.fixed_content)
            return True
        except Exception:
            return False
    
    def generate_and_apply_fix(
        self,
        repo_dir: str,
        error: ParsedError
    ) -> FixResult:
        """
        Generate and apply a fix in one operation.
        
        Args:
            repo_dir: Path to the repository
            error: ParsedError to fix
            
        Returns:
            FixResult with status
        """
        fix_result = self.generate_fix(repo_dir, error)
        
        if fix_result.success:
            applied = self.apply_fix(repo_dir, error, fix_result)
            if not applied:
                return FixResult(
                    success=False,
                    fixed_content=fix_result.fixed_content,
                    fix_description=fix_result.fix_description,
                    error="Failed to write fix to file"
                )
        
        return fix_result


# Singleton instance
llm_service = LLMService()
