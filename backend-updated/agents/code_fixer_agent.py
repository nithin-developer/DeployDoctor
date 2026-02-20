"""
Code Fixer Agent - Uses AI to fix identified code issues
"""
import os
import re
from typing import Any, Dict, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from agents.base_agent import BaseAgent
from analysis_schemas import CodeFix, BugType, FixStatus


class CodeFixerAgent(BaseAgent):
    """Agent responsible for fixing identified code issues"""
    
    def __init__(self):
        super().__init__(
            name="Code Fixer Agent",
            description="I analyze code errors and generate fixes. I can fix syntax errors, logic bugs, import issues, and more."
        )
    
    def _extract_first_json_object(self, text: str) -> Optional[str]:
        """Extract the first complete JSON object from text using bracket counting"""
        # Try to find JSON in markdown code blocks first
        code_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
        if code_block_match:
            return code_block_match.group(1)
        
        # Find the first opening brace
        start = text.find('{')
        if start == -1:
            return None
        
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
                    return text[start:i+1]
        
        return None
    
    def _repair_json_string(self, json_str: str) -> str:
        """Attempt to repair common JSON issues from LLM output"""
        # Replace unescaped newlines inside strings
        # This is tricky - we need to find strings and escape newlines within them
        result = []
        in_string = False
        escape_next = False
        i = 0
        
        while i < len(json_str):
            char = json_str[i]
            
            if escape_next:
                result.append(char)
                escape_next = False
                i += 1
                continue
            
            if char == '\\':
                result.append(char)
                escape_next = True
                i += 1
                continue
            
            if char == '"':
                in_string = not in_string
                result.append(char)
                i += 1
                continue
            
            if in_string and char == '\n':
                # Replace raw newline with escaped newline
                result.append('\\n')
                i += 1
                continue
            
            if in_string and char == '\r':
                # Skip carriage returns
                i += 1
                continue
            
            if in_string and char == '\t':
                # Replace raw tab with escaped tab
                result.append('\\t')
                i += 1
                continue
            
            result.append(char)
            i += 1
        
        return ''.join(result)
    
    def _parse_json_response(self, response_text: str) -> Optional[Dict]:
        """Parse JSON from LLM response with robust handling"""
        import json
        
        try:
            # Try direct parsing first
            return json.loads(response_text.strip())
        except json.JSONDecodeError:
            pass
        
        # Extract first JSON object
        json_str = self._extract_first_json_object(response_text)
        if json_str:
            # Try parsing as-is
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
            
            # Try repairing the JSON
            try:
                repaired = self._repair_json_string(json_str)
                return json.loads(repaired)
            except json.JSONDecodeError as e:
                print(f"JSON parse error after repair: {e}")
                
            # Last resort: try to extract just the essential fields with regex
            try:
                result = {}
                # Extract original_code
                orig_match = re.search(r'"original_code"\s*:\s*"((?:[^"\\]|\\.)*)"|"original_code"\s*:\s*\[(.*?)\]', json_str, re.DOTALL)
                if orig_match:
                    result['original_code'] = orig_match.group(1) or orig_match.group(2) or ""
                
                # Extract fixed_code
                fix_match = re.search(r'"fixed_code"\s*:\s*"((?:[^"\\]|\\.)*)"|"fixed_code"\s*:\s*\[(.*?)\]', json_str, re.DOTALL)
                if fix_match:
                    result['fixed_code'] = fix_match.group(1) or fix_match.group(2) or ""
                
                # Extract commit_message
                commit_match = re.search(r'"commit_message"\s*:\s*"([^"]*)"', json_str)
                if commit_match:
                    result['commit_message'] = commit_match.group(1)
                
                # Extract description
                desc_match = re.search(r'"description"\s*:\s*"([^"]*)"', json_str)
                if desc_match:
                    result['description'] = desc_match.group(1)
                
                if result.get('original_code') or result.get('fixed_code'):
                    print("  -> Recovered fix data via regex fallback")
                    return result
            except Exception:
                pass
        
        return None
    
    def _normalize_to_string(self, value: Any) -> str:
        """
        Normalize a value to a string.
        Handles: arrays (join with newlines), None, JSON-like strings, other types.
        """
        if value is None:
            return ""
        if isinstance(value, list):
            # Join array elements with newlines
            return '\n'.join(str(item) for item in value)
        if isinstance(value, dict):
            # If it's a dict, try to get a 'code' or 'text' field
            return value.get('code', value.get('text', str(value)))
        
        # Convert to string first
        s = str(value)
        
        # Check if it's a JSON array string like '["line1", "line2"]'
        s_stripped = s.strip()
        if s_stripped.startswith('[') and s_stripped.endswith(']'):
            try:
                import json
                parsed = json.loads(s_stripped)
                if isinstance(parsed, list):
                    return '\n'.join(str(item) for item in parsed)
            except (json.JSONDecodeError, ValueError):
                pass
        
        # Handle common patterns from LLM that look like array syntax
        # Pattern: '"line1",\n"line2"' or '"line1","line2"'
        if s_stripped.startswith('"') and '","' in s_stripped:
            try:
                # Try to parse as if it's array contents
                import json
                parsed = json.loads('[' + s_stripped + ']')
                if isinstance(parsed, list):
                    return '\n'.join(str(item) for item in parsed)
            except (json.JSONDecodeError, ValueError):
                pass
        
        return s
    
    def _clean_code_string(self, code: str) -> str:
        """
        Clean up code string that may have JSON artifacts, wrong escaping, etc.
        """
        if not code:
            return ""
        
        # Unescape common JSON escapes
        code = code.replace('\\"', '"')
        code = code.replace('\\n', '\n')
        code = code.replace('\\t', '\t')
        code = code.replace('\\\\', '\\')
        
        # Remove leading/trailing whitespace lines but preserve internal structure
        lines = code.split('\n')
        
        # Remove empty lines at start and end
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        
        return '\n'.join(lines)
    
    def _safe_get_string(self, data: Dict, key: str, default: str = "") -> str:
        """Safely get a string value from dict, normalizing and cleaning."""
        value = data.get(key, default)
        normalized = self._normalize_to_string(value)
        return self._clean_code_string(normalized)
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute code fixing for identified issues"""
        repo_path = context.get("repo_path")
        issues = context.get("issues", [])
        execution_errors = context.get("execution_errors", [])
        
        if not repo_path:
            return {"fixes": [], "error": "No repository path provided"}
        
        # Deduplicate issues by file+line (keep first occurrence)
        # Prioritize SYNTAX errors over LINTING
        priority_order = ['SYNTAX', 'INDENTATION', 'IMPORT', 'TYPE_ERROR', 'LOGIC', 'LINTING']
        
        def get_priority(bug_type: str) -> int:
            try:
                return priority_order.index(bug_type)
            except ValueError:
                return len(priority_order)
        
        # Sort by priority (lower = higher priority)
        sorted_issues = sorted(issues, key=lambda x: get_priority(x.get('bug_type', 'LINTING')))
        
        seen_locations = set()
        deduped_issues = []
        for issue in sorted_issues:
            file_path = issue.get('file_path', '')
            line_num = issue.get('line_number', 0)
            location_key = f"{file_path}:{line_num}"
            
            if location_key not in seen_locations:
                seen_locations.add(location_key)
                deduped_issues.append(issue)
        
        # Also dedupe execution errors by the same key
        for error in execution_errors:
            error_file = getattr(error, 'error_file', '')
            error_line = getattr(error, 'error_line', 0)
            location_key = f"{error_file}:{error_line}"
            seen_locations.add(location_key)  # Mark as seen so code issues don't duplicate
        
        # Check if there are SYNTAX or execution errors (excluding TEST_FAILURE) - if so, skip LINTING issues
        # LINTING issues are style/quality suggestions, not actual errors
        # After fixing SYNTAX errors, LINTING issues may no longer apply
        # TEST_FAILURE errors should NOT block LOGIC fixes since test failures often indicate logic errors
        syntax_execution_errors = [e for e in execution_errors 
                                    if getattr(e, 'error_type', '') not in ['TEST_FAILURE', 'LOGIC']]
        has_syntax_errors = len(syntax_execution_errors) > 0 or any(
            issue.get('bug_type') in ['SYNTAX', 'INDENTATION'] 
            for issue in deduped_issues
        )
        
        print(f"  DEBUG CodeFixer: syntax_execution_errors={len(syntax_execution_errors)}, has_syntax_errors={has_syntax_errors}")
        print(f"  DEBUG CodeFixer: deduped_issues types: {[i.get('bug_type') for i in deduped_issues[:5]]}")
        
        skipped_logic_issues = []  # Track skipped LOGIC issues to return to orchestrator
        
        if has_syntax_errors:
            # Filter to only critical issues when we have syntax errors
            critical_types = ['SYNTAX', 'INDENTATION', 'IMPORT', 'TYPE_ERROR']
            original_count = len(deduped_issues)
            # Separate out LOGIC issues for later processing
            skipped_logic_issues = [i for i in deduped_issues if i.get('bug_type') == 'LOGIC']
            deduped_issues = [i for i in deduped_issues if i.get('bug_type') in critical_types]
            skipped = original_count - len(deduped_issues)
            if skipped > 0:
                print(f"  Skipping {skipped} LINTING/LOGIC issues while fixing {len(syntax_execution_errors)} syntax errors")
                if skipped_logic_issues:
                    print(f"    -> {len(skipped_logic_issues)} LOGIC issues will be processed after syntax fixes")
        else:
            # No syntax errors - include LOGIC issues which often cause test failures
            print(f"  No syntax errors - processing all issues including LOGIC")
        
        # Also process TEST_FAILURE errors as actionable items (they indicate logic/correctness issues)
        test_failure_errors = [e for e in execution_errors 
                               if getattr(e, 'error_type', '') == 'TEST_FAILURE']
        if test_failure_errors:
            print(f"  Processing {len(test_failure_errors)} test failures as logic errors")
        
        print(f"CodeFixer: Processing {len(deduped_issues)} code issues (deduped from {len(issues)}) and {len(execution_errors)} execution errors")
        
        all_fixes = []
        
        # Fix issues from code analysis (deduplicated)
        for i, issue in enumerate(deduped_issues):
            print(f"  Fixing code issue {i+1}/{len(deduped_issues)}: {issue.get('bug_type')} in {issue.get('file_path')}")
            try:
                fix = await self._fix_issue(repo_path, issue)
                if fix:
                    all_fixes.append(fix)
                    print(f"    -> Generated fix")
                else:
                    print(f"    -> Failed to generate fix")
            except Exception as e:
                print(f"    -> Error generating fix: {type(e).__name__}: {str(e)[:100]}")
        
        # Fix issues from execution errors
        for i, error in enumerate(execution_errors):
            error_file = getattr(error, 'error_file', 'unknown')
            error_type = getattr(error, 'error_type', 'unknown')
            print(f"  Fixing execution error {i+1}/{len(execution_errors)}: {error_type} in {error_file}")
            try:
                fix = await self._fix_execution_error(repo_path, error)
                if fix:
                    all_fixes.append(fix)
                    print(f"    -> Generated fix")
                else:
                    print(f"    -> Failed to generate fix")
            except Exception as e:
                print(f"    -> Error generating fix: {type(e).__name__}: {str(e)[:100]}")
        
        # Apply all fixes to files
        print(f"Applying {len(all_fixes)} fixes to files...")
        applied_fixes = await self._apply_all_fixes(repo_path, all_fixes)
        
        return {
            "fixes": applied_fixes,
            "total_fixed": sum(1 for f in applied_fixes if f.status == FixStatus.FIXED),
            "total_failed": sum(1 for f in applied_fixes if f.status == FixStatus.FAILED),
            "skipped_logic_issues": skipped_logic_issues  # Return skipped LOGIC issues for next iteration
        }
    
    async def _fix_issue(self, repo_path: str, issue: Dict[str, Any]) -> Optional[CodeFix]:
        """Fix a single code issue"""
        file_path = issue.get("file_path")
        line_number = issue.get("line_number", 1)
        bug_type = issue.get("bug_type", "LINTING")
        description = issue.get("description", "")
        
        if not file_path:
            return None
        
        full_path = os.path.join(repo_path, file_path)
        if not os.path.exists(full_path):
            return None
        
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception:
            return None
        
        # Get context around the error line
        start_line = max(0, line_number - 5)
        end_line = min(len(lines), line_number + 5)
        context_lines = lines[start_line:end_line]
        context_code = '\n'.join(f"{i+start_line+1}: {line}" for i, line in enumerate(context_lines))
        
        # Generate fix using AI
        fix_result = await self._generate_fix(
            file_path=file_path,
            full_content=content,
            context_code=context_code,
            line_number=line_number,
            bug_type=bug_type,
            description=description
        )
        
        if fix_result:
            return CodeFix(
                file_path=file_path,
                bug_type=BugType(bug_type) if bug_type in [b.value for b in BugType] else BugType.LINTING,
                line_number=line_number,
                commit_message=self._safe_get_string(fix_result, "commit_message", f"Fix {bug_type} issue in {file_path}"),
                status=FixStatus.FIXED,
                original_code=self._safe_get_string(fix_result, "original_code"),
                fixed_code=self._safe_get_string(fix_result, "fixed_code"),
                description=self._safe_get_string(fix_result, "description", description)
            )
        
        return None
    
    async def _fix_execution_error(self, repo_path: str, error: Any) -> Optional[CodeFix]:
        """Fix an error from code execution"""
        error_file = getattr(error, 'error_file', None)
        error_line = getattr(error, 'error_line', None)
        error_type = getattr(error, 'error_type', 'RuntimeError')
        stderr = getattr(error, 'stderr', '')
        
        print(f"    Debug: error_file={error_file}, error_line={error_line}, error_type={error_type}")
        print(f"    Debug: stderr length={len(stderr)}")
        
        if not error_file:
            print(f"    Skipping: No error_file in execution error")
            return None
        
        if not stderr:
            print(f"    Skipping: No stderr in execution error")
            return None
        
        # Normalize file path
        if os.path.isabs(error_file):
            relative_path = os.path.relpath(error_file, repo_path)
        else:
            relative_path = error_file
        
        full_path = os.path.join(repo_path, relative_path)
        if not os.path.exists(full_path):
            # Try to find the file
            for root, dirs, files in os.walk(repo_path):
                for f in files:
                    if f == os.path.basename(error_file):
                        full_path = os.path.join(root, f)
                        relative_path = os.path.relpath(full_path, repo_path)
                        break
        
        if not os.path.exists(full_path):
            return None
        
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            return None
        
        # Map error type to BugType
        bug_type = self._map_error_to_bug_type(error_type)
        
        # Generate fix using AI
        fix_result = await self._generate_fix_from_error(
            file_path=relative_path,
            full_content=content,
            error_message=stderr,
            error_line=error_line,
            error_type=error_type
        )
        
        if fix_result:
            return CodeFix(
                file_path=relative_path,
                bug_type=bug_type,
                line_number=error_line or 1,
                commit_message=self._safe_get_string(fix_result, "commit_message", f"Fix {error_type} in {relative_path}"),
                status=FixStatus.FIXED,
                original_code=self._safe_get_string(fix_result, "original_code"),
                fixed_code=self._safe_get_string(fix_result, "fixed_code"),
                description=self._safe_get_string(fix_result, "description", stderr[:200])
            )
        
        return None
    
    def _map_error_to_bug_type(self, error_type: str) -> BugType:
        """Map Python error type to BugType"""
        error_mapping = {
            'SyntaxError': BugType.SYNTAX,
            'IndentationError': BugType.INDENTATION,
            'TabError': BugType.INDENTATION,
            'NameError': BugType.LOGIC,
            'TypeError': BugType.TYPE_ERROR,
            'ImportError': BugType.IMPORT,
            'ModuleNotFoundError': BugType.IMPORT,
            'AttributeError': BugType.LOGIC,
            'ValueError': BugType.LOGIC,
            'KeyError': BugType.LOGIC,
            'IndexError': BugType.LOGIC,
            'TEST_FAILURE': BugType.TEST_FAILURE,
            'AssertionError': BugType.TEST_FAILURE,
            'LINTING': BugType.LINTING,
            'TYPE_ERROR': BugType.TYPE_ERROR,
            'UNDEFINED_NAME': BugType.LOGIC,
            'UNUSED_VARIABLE': BugType.LINTING,
            'UNUSED_IMPORT': BugType.IMPORT,
            # JavaScript/TypeScript errors
            'JSX_ERROR': BugType.SYNTAX,
            'REACT_WARNING': BugType.LINTING,
            'CONSOLE_STATEMENT': BugType.LINTING,
            'DEBUGGER': BugType.LINTING,
            'EMPTY_CATCH': BugType.LOGIC,
            'ASSIGNMENT_IN_CONDITION': BugType.LOGIC,
            'LOOSE_EQUALITY': BugType.LINTING,
            'LOOSE_INEQUALITY': BugType.LINTING,
            # Java errors
            'JAVA_ERROR': BugType.SYNTAX,
            'JAVA_WARNING': BugType.LINTING,
            'MAVEN_ERROR': BugType.RUNTIME,
            'GRADLE_ERROR': BugType.RUNTIME,
        }
        return error_mapping.get(error_type, BugType.LINTING)
    
    async def _generate_fix(self, file_path: str, full_content: str, context_code: str,
                           line_number: int, bug_type: str, description: str) -> Optional[Dict]:
        """Generate a fix for a code issue using AI"""
        
        system_prompt = """You are a SENIOR code reviewer fixing production code. Your fixes must be professional and context-aware.

CRITICAL RULES:
1. UNDERSTAND THE CONTEXT - Read the surrounding code to understand the developer's intent
2. FIX PROPERLY - Don't use lazy placeholders like `pass`, `range(0)`, or empty blocks
3. IF CODE IS UNNECESSARY - REMOVE IT entirely instead of making it a no-op
4. IF CODE IS INCOMPLETE - Complete it based on context (variable names, function purpose, etc.)
5. PRESERVE FUNCTIONALITY - Your fix should make the code work as the developer intended
6. NEVER USE RELATIVE IMPORTS - Do NOT use `from .module import` syntax. Keep imports simple like `from module import`

BAD FIXES (NEVER DO THIS):
- `for _ in range(0):` - This is pointless, remove the loop entirely
- Adding `pass` to empty blocks without purpose
- `if True:` or `if False:` placeholders
- `from .module import something` - Relative imports break standalone scripts

GOOD FIXES:
- Remove unnecessary/incomplete code that serves no purpose
- Complete code based on context
- Fix syntax while preserving the developer's clear intent
- Keep imports simple: `from calculator import multiply` is fine

Respond in JSON format:
{
    "original_code": "the exact original problematic code (include full lines)",
    "fixed_code": "the corrected code (can be empty string to remove code)",
    "description": "brief explanation of what was fixed and WHY",
    "commit_message": "concise commit message for this fix"
}

IMPORTANT: 
- The original_code must be an EXACT character-by-character match of text in the file
- Include the FULL LINE(s) in original_code
- If the problematic code should be removed entirely, set fixed_code to ""
- Include enough context to make original_code unique in the file"""

        human_prompt = f"""File: {file_path}
Issue Type: {bug_type}
Line Number: {line_number}
Issue Description: {description}

Code context around line {line_number}:
```
{context_code}
```

Full file content:
```
{full_content[:6000]}
```

Generate the fix for this issue."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            response_text = response.content
            
            # Parse JSON response using robust method
            return self._parse_json_response(response_text)
                
        except Exception as e:
            print(f"Error generating fix: {str(e)}")
        
        return None
    
    async def _generate_fix_from_error(self, file_path: str, full_content: str,
                                       error_message: str, error_line: Optional[int],
                                       error_type: str) -> Optional[Dict]:
        """Generate a fix based on runtime/syntax error or test failure"""
        
        # Different prompts for test failures vs syntax errors
        is_test_failure = error_type in ['TEST_FAILURE', 'AssertionError'] or 'assert' in error_message.lower()
        
        if is_test_failure:
            system_prompt = """You are a SENIOR code reviewer fixing a LOGIC BUG that caused a test to fail.

CRITICAL: The test is CORRECT - the code being tested has a BUG. Fix the SOURCE CODE, not the test.

COMMON LOGIC BUGS TO LOOK FOR:
1. Wrong operator: Using + instead of *, - instead of /, etc.
2. Wrong return value: Returning the wrong variable or calculation
3. Off-by-one errors: Wrong loop bounds, wrong indices
4. Inverted logic: Using > instead of <, and instead of or
5. Wrong function called: Calling the wrong helper/method
6. Missing negation: Forgot to use 'not' or '-'

ANALYSIS STEPS:
1. Read the test failure message to understand what was expected vs actual
2. Look at the function being tested
3. Find the logical error in the implementation
4. Fix the LOGIC, not just syntax

Respond in JSON format:
{
    "original_code": "the exact original buggy code line(s)",
    "fixed_code": "the corrected code with proper logic",
    "description": "explanation of the logic bug and how you fixed it",
    "commit_message": "fix: correct logic in <function_name>"
}

IMPORTANT:
- The original_code must be an EXACT character-by-character match 
- Include the FULL LINE(s), not partial
- Focus on the LOGIC ERROR causing the test failure"""
        else:
            system_prompt = """You are a SENIOR code reviewer fixing production code. Your fixes must be professional and context-aware.

CRITICAL RULES:
1. UNDERSTAND THE CONTEXT - Read the surrounding code to understand the developer's intent
2. FIX PROPERLY - Don't use lazy placeholders like `pass`, `range(0)`, or empty blocks
3. IF CODE IS UNNECESSARY - REMOVE IT entirely instead of making it a no-op
4. IF CODE IS INCOMPLETE - Complete it based on context (variable names, function purpose, etc.)
5. PRESERVE FUNCTIONALITY - Your fix should make the code work as the developer intended
6. NEVER USE RELATIVE IMPORTS - Do NOT use `from .module import` syntax. Keep imports simple.

BAD FIXES (NEVER DO THIS):
- `for _ in range(0):` - This is pointless, remove the loop entirely
- Adding `pass` to empty blocks without purpose
- `if True:` or `if False:` placeholders
- Comments like `# TODO: implement`
- `from .module import something` - This breaks standalone scripts

GOOD FIXES:
- Remove unnecessary/incomplete code that serves no purpose
- Complete code based on context (e.g., if looping over items, use existing variables)
- Fix syntax while preserving the developer's clear intent
- Keep imports simple: `from calculator import multiply` is correct

Respond in JSON format:
{
    "original_code": "the exact original problematic code (include full lines, multi-line if needed)",
    "fixed_code": "the corrected code (can be empty string if code should be removed)",
    "description": "brief explanation of what was fixed and WHY",
    "commit_message": "concise commit message for this fix"
}

IMPORTANT:
- The original_code must be an EXACT character-by-character match of text in the file
- Include the FULL LINE(s) in original_code, not partial lines
- If the problematic code should be removed entirely, set fixed_code to empty string ""
- Include enough surrounding lines to make original_code unique in the file"""

        lines = full_content.split('\n')
        if error_line:
            start = max(0, error_line - 5)
            end = min(len(lines), error_line + 5)
            context = '\n'.join(f"{i+1}: {lines[i]}" for i in range(start, end))
        else:
            context = '\n'.join(f"{i+1}: {line}" for i, line in enumerate(lines[:30]))

        if is_test_failure:
            human_prompt = f"""File: {file_path}
Error Type: TEST FAILURE (the code has a LOGIC BUG)
Error Line: {error_line or 'Unknown'}

Test Failure Message:
```
{error_message[:2000]}
```

Code in {file_path} (this is the code WITH THE BUG):
```
{context}
```

Full file content:
```
{full_content[:6000]}
```

Find and fix the LOGIC ERROR in this code that caused the test to fail. The test is correct - the code is wrong."""
        else:
            human_prompt = f"""File: {file_path}
Error Type: {error_type}
Error Line: {error_line or 'Unknown'}

Error Message:
```
{error_message[:1500]}
```

Code context:
```
{context}
```

Full file content:
```
{full_content[:6000]}
```

Generate the fix to resolve this error."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            response_text = response.content
            
            # Parse JSON response using robust method
            return self._parse_json_response(response_text)
                
        except Exception as e:
            print(f"Error generating fix from error: {str(e)}")
        
        return None
    
    def _try_line_based_fix(self, lines: List[str], fix: CodeFix) -> bool:
        """
        Try to apply fix using line-based matching when exact match fails.
        Returns True if fix was applied successfully, modifies lines in-place.
        """
        if not fix.line_number or fix.line_number < 1:
            return False
        
        line_idx = fix.line_number - 1
        if line_idx >= len(lines):
            return False
        
        original_lines = fix.original_code.split('\n') if fix.original_code else []
        if not original_lines:
            return False
        
        # Get the number of lines in the original code
        num_original_lines = len(original_lines)
        
        # Check if we have enough lines in the file
        if line_idx + num_original_lines > len(lines):
            return False
        
        # Try to match based on the first line of original code (stripped)
        first_orig_stripped = original_lines[0].strip()
        actual_first_stripped = lines[line_idx].strip()
        
        # Check if the first line matches (allow whitespace differences)
        if first_orig_stripped and first_orig_stripped != actual_first_stripped:
            # Try fuzzy match - check if key parts are present
            key_parts = [p for p in first_orig_stripped.split() if len(p) > 2]
            matches = sum(1 for p in key_parts if p in actual_first_stripped)
            if matches < len(key_parts) * 0.5:  # Less than 50% match
                return False
        
        # If fix.fixed_code is empty, remove the lines
        if not fix.fixed_code or fix.fixed_code.strip() == '':
            # Remove the lines
            for _ in range(num_original_lines):
                if line_idx < len(lines):
                    lines.pop(line_idx)
            return True
        
        # Replace lines
        fixed_lines = fix.fixed_code.split('\n')
        
        # Remove original lines
        for _ in range(num_original_lines):
            if line_idx < len(lines):
                lines.pop(line_idx)
        
        # Insert fixed lines
        for i, new_line in enumerate(fixed_lines):
            lines.insert(line_idx + i, new_line)
        
        return True
    
    async def _apply_all_fixes(self, repo_path: str, fixes: List[CodeFix]) -> List[CodeFix]:
        """Apply all fixes to the repository files"""
        applied_fixes = []
        
        # Group fixes by file for efficiency
        fixes_by_file: Dict[str, List[CodeFix]] = {}
        for fix in fixes:
            if fix.file_path not in fixes_by_file:
                fixes_by_file[fix.file_path] = []
            fixes_by_file[fix.file_path].append(fix)
        
        for file_path, file_fixes in fixes_by_file.items():
            full_path = os.path.join(repo_path, file_path)
            
            if not os.path.exists(full_path):
                for fix in file_fixes:
                    fix.status = FixStatus.FAILED
                    fix.description = (fix.description or "") + " [File not found]"
                    applied_fixes.append(fix)
                continue
            
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                lines = content.split('\n')
                
                # Sort fixes by line number descending (apply from bottom up to avoid line shifts)
                file_fixes_sorted = sorted(file_fixes, key=lambda f: f.line_number or 0, reverse=True)
                
                # Apply each fix
                for fix in file_fixes_sorted:
                    if not fix.original_code:
                        fix.status = FixStatus.FAILED
                        fix.description = (fix.description or "") + " [Missing original code]"
                        applied_fixes.append(fix)
                        continue
                    
                    # Re-read current content state for each fix
                    content = '\n'.join(lines)
                    
                    # Try exact match first
                    if fix.original_code in content:
                        content = content.replace(fix.original_code, fix.fixed_code or "", 1)
                        lines = content.split('\n')
                        fix.status = FixStatus.FIXED
                        if not fix.fixed_code:
                            fix.description = (fix.description or "") + " [Code removed]"
                    else:
                        # Try line-based replacement as fallback
                        line_fixed = self._try_line_based_fix(lines, fix)
                        if line_fixed:
                            fix.status = FixStatus.FIXED
                            if not fix.fixed_code:
                                fix.description = (fix.description or "") + " [Code removed]"
                        else:
                            fix.status = FixStatus.FAILED
                            fix.description = (fix.description or "") + " [Original code not found in file]"
                    
                    applied_fixes.append(fix)
                
                # Write updated content if changed
                final_content = '\n'.join(lines)
                if final_content != original_content:
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(final_content)
                        
            except Exception as e:
                for fix in file_fixes:
                    fix.status = FixStatus.FAILED
                    fix.description = (fix.description or "") + f" [Error: {str(e)}]"
                    applied_fixes.append(fix)
        
        return applied_fixes
