"""
Code Review Agent - Performs comprehensive line by line code analysis
"""
import os
import re
from typing import Any, Dict, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from agents.base_agent import BaseAgent
from models import CodeFix, BugType, FixStatus


class CodeReviewAgent(BaseAgent):
    """Agent responsible for comprehensive line-by-line code review"""
    
    def __init__(self):
        super().__init__(
            name="Code Review Agent",
            description="I analyze code line by line to detect bugs, linting issues, syntax errors, logic problems, type errors, import issues, and indentation problems."
        )
        self.supported_extensions = {
            '.py': 'python',
            '.js': 'javascript', 
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.go': 'go',
            '.rs': 'rust'
        }
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute comprehensive code review on the repository"""
        repo_path = context.get("repo_path")
        if not repo_path:
            return {"issues": [], "error": "No repository path provided"}
        
        all_issues = []
        files_analyzed = 0
        
        # Walk through all files in the repository
        for root, dirs, files in os.walk(repo_path):
            # Skip hidden directories and common non-code directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in 
                      ['node_modules', '__pycache__', 'venv', '.venv', 'dist', 'build', 
                       'vendor', '.git', '.idea', '__snapshots__']]
            
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in self.supported_extensions:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, repo_path)
                    language = self.supported_extensions[ext]
                    
                    try:
                        issues = await self._analyze_file_deeply(
                            file_path, relative_path, language
                        )
                        all_issues.extend(issues)
                        files_analyzed += 1
                    except Exception as e:
                        print(f"Error analyzing {relative_path}: {str(e)}")
        
        return {
            "issues": all_issues,
            "files_analyzed": files_analyzed,
            "total_issues": len(all_issues)
        }
    
    async def _analyze_file_deeply(self, file_path: str, relative_path: str, 
                                   language: str) -> List[Dict[str, Any]]:
        """Perform deep analysis of a single file"""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception:
            return issues
        
        # Skip empty files or very large files
        if not content.strip():
            return issues
        
        if len(lines) > 500:
            # For large files, analyze in chunks
            issues.extend(await self._analyze_in_chunks(content, relative_path, language, lines))
        else:
            # Analyze entire file
            issues.extend(await self._analyze_full_file(content, relative_path, language))
        
        return issues
    
    async def _analyze_full_file(self, content: str, file_path: str, 
                                 language: str) -> List[Dict[str, Any]]:
        """Analyze a complete file"""
        
        system_prompt = f"""You are an expert {language} code reviewer performing a thorough line-by-line analysis.

Your task is to identify ALL issues in the code including:
1. SYNTAX errors - invalid syntax, missing brackets, wrong operators
2. LOGIC bugs - incorrect conditions, wrong variable usage, potential null/undefined errors
3. TYPE_ERROR - type mismatches, wrong argument types
4. IMPORT issues - ONLY report imports that are ACTUALLY broken (module not found, circular imports)
5. INDENTATION problems - inconsistent indentation, wrong nesting
6. LINTING issues - code style problems, naming conventions

IMPORTANT FOR IMPORTS:
- `from calculator import multiply` is VALID if calculator.py exists in the same directory
- Do NOT suggest relative imports like `from .calculator import` - these break standalone scripts
- Only report IMPORT issues if the import will actually fail at runtime

For EACH issue found, provide:
- line_number: the exact line number
- bug_type: one of [SYNTAX, LOGIC, TYPE_ERROR, IMPORT, INDENTATION, LINTING]
- description: clear explanation of what's wrong
- original_code: the EXACT problematic code (copy it character-for-character)
- fixed_code: the corrected code
- severity: HIGH, MEDIUM, or LOW

Respond in JSON format:
{{
    "issues": [
        {{
            "line_number": <number>,
            "bug_type": "<type>",
            "description": "<description>",
            "original_code": "<exact original code>",
            "fixed_code": "<corrected code>",
            "severity": "<severity>"
        }}
    ]
}}

If no issues found, return: {{"issues": []}}

Be thorough but accurate. Only report real issues, not style preferences unless they're severe."""

        human_prompt = f"""Analyze this {language} file: {file_path}

```{language}
{content[:12000]}
```

Perform a thorough line-by-line review. Identify ALL bugs, errors, and issues."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            issues = self._parse_analysis_response(response.content, file_path)
            return issues
            
        except Exception as e:
            print(f"LLM analysis error for {file_path}: {str(e)}")
            return []
    
    async def _analyze_in_chunks(self, content: str, file_path: str, 
                                 language: str, lines: List[str]) -> List[Dict[str, Any]]:
        """Analyze a large file in chunks"""
        all_issues = []
        chunk_size = 100  # lines per chunk
        
        for i in range(0, len(lines), chunk_size):
            chunk_lines = lines[i:i + chunk_size]
            chunk_content = '\n'.join(chunk_lines)
            start_line = i + 1
            
            chunk_issues = await self._analyze_chunk(
                chunk_content, file_path, language, start_line
            )
            all_issues.extend(chunk_issues)
        
        return all_issues
    
    async def _analyze_chunk(self, chunk: str, file_path: str, 
                            language: str, start_line: int) -> List[Dict[str, Any]]:
        """Analyze a chunk of code"""
        
        system_prompt = f"""You are an expert {language} code reviewer. Analyze this code chunk.

Identify issues including: SYNTAX, LOGIC, TYPE_ERROR, IMPORT, INDENTATION, LINTING

IMPORTANT FOR IMPORTS:
- Simple imports like `from calculator import multiply` are VALID if the file exists
- Do NOT suggest relative imports (from .module import) - they break standalone scripts

Respond in JSON:
{{
    "issues": [
        {{
            "line_number": <number relative to chunk>,
            "bug_type": "<type>",
            "description": "<description>",
            "original_code": "<exact code>",
            "fixed_code": "<fixed code>"
        }}
    ]
}}

Line numbers are relative to this chunk (starting at 1). Only report clear issues."""

        human_prompt = f"""File: {file_path} (lines {start_line} to {start_line + len(chunk.split(chr(10))) - 1})

```{language}
{chunk}
```

Find all issues."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            issues = self._parse_analysis_response(response.content, file_path)
            
            # Adjust line numbers to file-level
            for issue in issues:
                issue['line_number'] = issue.get('line_number', 1) + start_line - 1
            
            return issues
            
        except Exception as e:
            print(f"Chunk analysis error: {str(e)}")
            return []
    
    def _parse_analysis_response(self, response_text: str, 
                                 file_path: str) -> List[Dict[str, Any]]:
        """Parse LLM response into issue dictionaries"""
        issues = []
        
        try:
            import json
            
            # Clean response text
            cleaned = response_text.strip()
            
            # Try to find JSON block in markdown code blocks first
            code_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', cleaned)
            if code_block_match:
                cleaned = code_block_match.group(1)
            
            # Try direct JSON parsing first
            try:
                data = json.loads(cleaned)
                raw_issues = data.get("issues", [])
            except json.JSONDecodeError:
                # Find the first complete JSON object using bracket counting
                json_str = self._extract_first_json_object(cleaned)
                if json_str:
                    data = json.loads(json_str)
                    raw_issues = data.get("issues", [])
                else:
                    print(f"Could not extract JSON from response")
                    return issues
            
            for issue in raw_issues:
                bug_type = issue.get("bug_type", "LINTING").upper()
                if bug_type not in [bt.value for bt in BugType]:
                    bug_type = "LINTING"
                
                issues.append({
                    "file_path": file_path,
                    "line_number": issue.get("line_number", 1),
                    "bug_type": bug_type,
                    "description": issue.get("description", ""),
                    "original_code": issue.get("original_code", ""),
                    "fixed_code": issue.get("fixed_code", ""),
                    "severity": issue.get("severity", "MEDIUM")
                })
                    
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {str(e)}")
        except Exception as e:
            print(f"Parse error: {str(e)}")
        
        return issues
    
    def _extract_first_json_object(self, text: str) -> Optional[str]:
        """Extract the first complete JSON object from text using bracket counting"""
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
