"""Debug script for the agent pipeline."""
import asyncio
import shutil
from pathlib import Path
from agents.sandbox_executor_agent import SandboxExecutorAgent
from agents.code_fixer_agent import CodeFixerAgent


async def test_fixes_step_by_step():
    print('=== Testing Fixes Step by Step ===')
    
    # Clone fresh
    repo_path = Path('temp_test_debug')
    if repo_path.exists():
        shutil.rmtree(repo_path)
    
    import subprocess
    subprocess.run(['git', 'clone', '--depth', '1', 'https://github.com/nithin-developer/test', str(repo_path)], capture_output=True)
    
    sandbox = SandboxExecutorAgent()
    fixer = CodeFixerAgent()
    
    for iteration in range(5):
        print(f'\n=== Iteration {iteration + 1} ===')
        
        # Show current file state
        app_file = repo_path / 'app.py'
        content = app_file.read_text(encoding='utf-8')
        lines = content.split('\n')
        print(f'File state (last 5 lines):')
        for i in range(max(0, len(lines) - 5), len(lines)):
            print(f'  Line {i+1}: {repr(lines[i])}')
        
        # Run sandbox
        result = await sandbox.execute({'repo_path': str(repo_path)})
        errors = result.data.get('errors', []) if result.data else []
        print(f'\nErrors found: {len(errors)}')
        for err in errors:
            print(f'  - {err}')
        
        if not errors:
            print('No more errors!')
            break
        
        # Convert and fix
        converted = [{
            'file_path': err.get('file', ''),
            'line_number': err.get('line', 1),
            'message': err.get('message', ''),
            'bug_type': 'SYNTAX' if 'Syntax' in str(err.get('type', '')) else 'UNKNOWN'
        } for err in errors]
        
        fix_result = await fixer.execute({
            'repo_path': str(repo_path),
            'errors': converted,
            'apply_fixes': True,
            'max_fixes': 1
        })
        
        if fix_result.data:
            fixes = fix_result.data.get('fixes', [])
            applied = fix_result.data.get('fixes_applied', 0)
            print(f'\nFixes applied: {applied}')
            for f in fixes:
                print(f'  File: {f.get("file_path")}')
                print(f'  Line: {f.get("line_number")}')
                print(f'  Original: {repr(f.get("original_code"))}')
                print(f'  Fixed: {repr(f.get("fixed_code"))}')
                print(f'  Success: {f.get("success")}')
    
    # Cleanup
    if repo_path.exists():
        shutil.rmtree(repo_path)


if __name__ == '__main__':
    asyncio.run(test_fixes_step_by_step())
