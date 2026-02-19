"""
Test Generator Agent - Generates test cases for code using AI
"""
import os
import re
from typing import Any, Dict, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from agents.base_agent import BaseAgent


class GeneratedTest:
    """Represents a generated test case"""
    def __init__(self, file_path: str, test_name: str, test_code: str, 
                 target_file: str, target_function: Optional[str] = None,
                 test_framework: str = "pytest"):
        self.file_path = file_path
        self.test_name = test_name
        self.test_code = test_code
        self.target_file = target_file
        self.target_function = target_function
        self.test_framework = test_framework
    
    def to_dict(self) -> Dict:
        return {
            "file_path": self.file_path,
            "test_name": self.test_name,
            "test_code": self.test_code,
            "target_file": self.target_file,
            "target_function": self.target_function,
            "test_framework": self.test_framework
        }


class TestGeneratorAgent(BaseAgent):
    """Agent responsible for generating test cases"""
    
    def __init__(self):
        super().__init__(
            name="Test Generator Agent",
            description="I analyze code and generate comprehensive test cases using pytest and unittest frameworks."
        )
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate test cases for the repository"""
        repo_path = context.get("repo_path")
        if not repo_path:
            return {"generated_tests": [], "error": "No repository path provided"}
        
        generated_tests = []
        files_analyzed = 0
        
        # Find Python files to generate tests for
        python_files = self._find_testable_files(repo_path)
        
        print(f"\nTestGenerator: Found {len(python_files)} files to generate tests for")
        
        for file_info in python_files:
            file_path = file_info["path"]
            relative_path = file_info["relative"]
            
            try:
                tests = await self._generate_tests_for_file(repo_path, relative_path)
                if tests:
                    generated_tests.extend(tests)
                    files_analyzed += 1
                    print(f"  Generated {len(tests)} tests for {relative_path}")
            except Exception as e:
                print(f"  Error generating tests for {relative_path}: {str(e)}")
        
        # Write generated tests to files
        written_tests = await self._write_test_files(repo_path, generated_tests)
        
        return {
            "generated_tests": [t.to_dict() for t in written_tests],
            "files_analyzed": files_analyzed,
            "total_tests_generated": len(written_tests)
        }
    
    def _find_testable_files(self, repo_path: str) -> List[Dict]:
        """Find Python files that should have tests generated"""
        testable_files = []
        
        skip_dirs = {'node_modules', '__pycache__', 'venv', '.venv', 'dist', 
                     'build', '.git', 'tests', 'test', '__tests__'}
        skip_patterns = {'test_', '_test.py', 'tests.py', 'conftest.py', 
                        'setup.py', '__init__.py'}
        
        for root, dirs, files in os.walk(repo_path):
            # Skip test directories and common non-source directories
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
            
            for file in files:
                if file.endswith('.py'):
                    # Skip test files and config files
                    if any(pattern in file.lower() for pattern in skip_patterns):
                        continue
                    
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, repo_path)
                    
                    # Check if file has testable content (functions/classes)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        # Skip empty files or files with no functions/classes
                        if not content.strip():
                            continue
                        
                        if 'def ' in content or 'class ' in content:
                            testable_files.append({
                                "path": file_path,
                                "relative": relative_path,
                                "content": content
                            })
                    except Exception:
                        continue
        
        return testable_files[:5]  # Limit to 5 files for efficiency
    
    async def _generate_tests_for_file(self, repo_path: str, 
                                       relative_path: str) -> List[GeneratedTest]:
        """Generate tests for a single file using AI"""
        full_path = os.path.join(repo_path, relative_path)
        
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            return []
        
        # Extract functions and classes for context
        functions = self._extract_functions(content)
        classes = self._extract_classes(content)
        
        if not functions and not classes:
            return []
        
        system_prompt = """You are an expert Python test engineer. Generate comprehensive test cases.

IMPORTANT RULES:
1. Generate tests using pytest (preferred) or unittest
2. Include edge cases and error handling tests
3. Use descriptive test names following test_<function>_<scenario> pattern
4. Include docstrings explaining what each test verifies
5. Mock external dependencies when needed
6. Return ONLY valid JSON

Output format:
{
    "tests": [
        {
            "test_name": "test_function_name_scenario",
            "test_framework": "pytest",
            "target_function": "function_being_tested",
            "test_code": "def test_function_name_scenario():\\n    # test code here\\n    assert result == expected"
        }
    ]
}"""

        human_prompt = f"""Generate test cases for this Python file:

File: {relative_path}

```python
{content[:3000]}  # Truncate for API limits
```

Functions found: {', '.join(functions[:10])}
Classes found: {', '.join(classes[:5])}

Generate 2-4 meaningful tests that cover:
1. Normal operation (happy path)
2. Edge cases
3. Error handling (if applicable)

Return ONLY the JSON response."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            response_text = response.content
            
            # Parse response
            tests_data = self._parse_json_response(response_text)
            
            if not tests_data or "tests" not in tests_data:
                return []
            
            generated_tests = []
            test_file_name = self._get_test_file_name(relative_path)
            
            for test_info in tests_data.get("tests", []):
                test = GeneratedTest(
                    file_path=test_file_name,
                    test_name=test_info.get("test_name", "test_generated"),
                    test_code=test_info.get("test_code", ""),
                    target_file=relative_path,
                    target_function=test_info.get("target_function"),
                    test_framework=test_info.get("test_framework", "pytest")
                )
                generated_tests.append(test)
            
            return generated_tests
            
        except Exception as e:
            print(f"    Error in LLM call: {str(e)}")
            return []
    
    def _extract_functions(self, content: str) -> List[str]:
        """Extract function names from Python code"""
        pattern = r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        matches = re.findall(pattern, content)
        # Filter out private/dunder methods
        return [m for m in matches if not m.startswith('_')]
    
    def _extract_classes(self, content: str) -> List[str]:
        """Extract class names from Python code"""
        pattern = r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[:\(]'
        return re.findall(pattern, content)
    
    def _get_test_file_name(self, source_file: str) -> str:
        """Generate test file name from source file"""
        dir_name = os.path.dirname(source_file)
        base_name = os.path.basename(source_file)
        name_without_ext = os.path.splitext(base_name)[0]
        
        test_file_name = f"test_{name_without_ext}.py"
        
        # Put tests in tests/ directory
        return os.path.join("tests", test_file_name)
    
    def _parse_json_response(self, response_text: str) -> Optional[Dict]:
        """Parse JSON from LLM response"""
        import json
        
        # Try direct parsing
        try:
            return json.loads(response_text.strip())
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response_text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON object
        start = response_text.find('{')
        if start != -1:
            depth = 0
            for i in range(start, len(response_text)):
                if response_text[i] == '{':
                    depth += 1
                elif response_text[i] == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(response_text[start:i+1])
                        except json.JSONDecodeError:
                            pass
                        break
        
        return None
    
    async def _write_test_files(self, repo_path: str, 
                                tests: List[GeneratedTest]) -> List[GeneratedTest]:
        """Write generated tests to files"""
        written_tests = []
        
        # Group tests by file
        tests_by_file: Dict[str, List[GeneratedTest]] = {}
        for test in tests:
            if test.file_path not in tests_by_file:
                tests_by_file[test.file_path] = []
            tests_by_file[test.file_path].append(test)
        
        # Create tests directory if needed
        tests_dir = os.path.join(repo_path, "tests")
        os.makedirs(tests_dir, exist_ok=True)
        
        # Create __init__.py for tests package
        init_file = os.path.join(tests_dir, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                f.write("# Auto-generated test package\n")
        
        for test_file, file_tests in tests_by_file.items():
            full_path = os.path.join(repo_path, test_file)
            
            # Create directory if needed
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            # Build file content
            imports = set()
            test_codes = []
            target_modules = set()
            
            for test in file_tests:
                if test.test_framework == "pytest":
                    imports.add("import pytest")
                else:
                    imports.add("import unittest")
                
                # Add import for the target module
                target_module = test.target_file.replace('/', '.').replace('\\', '.')
                target_module = target_module.rsplit('.py', 1)[0]
                if target_module:
                    target_modules.add(target_module)
                
                test_codes.append(test.test_code)
            
            # Build proper imports - add sys.path for tests in subdirectory
            sys_path_setup = """import sys
import os

# Add parent directory to path so we can import modules from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""
            
            for mod in target_modules:
                imports.add(f"from {mod} import *")
            
            # Write file - include sys.path setup BEFORE imports
            content = f'''"""
Auto-generated tests by AI Repository Analyser
Target files: {', '.join(set(t.target_file for t in file_tests))}
"""
{sys_path_setup}
{chr(10).join(sorted(imports))}


{chr(10).join(test_codes)}
'''
            
            try:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                written_tests.extend(file_tests)
                print(f"  Wrote test file: {test_file}")
            except Exception as e:
                print(f"  Error writing {test_file}: {str(e)}")
        
        return written_tests
