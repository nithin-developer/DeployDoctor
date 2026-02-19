import os
import uuid
import shutil
import tempfile
import subprocess
from typing import Optional, Tuple
from datetime import datetime
from pathlib import Path

from git import Repo, GitCommandError

from schemas.agent import ProjectType
from utils.branch import generate_branch_name, extract_repo_info


class GitService:
    """Service for handling Git repository operations."""
    
    def __init__(self, temp_base_dir: Optional[str] = None):
        """
        Initialize GitService.
        
        Args:
            temp_base_dir: Base directory for temp folders. 
                          If None, uses system temp directory.
        """
        self.temp_base_dir = temp_base_dir or tempfile.gettempdir()
    
    def _generate_temp_dir(self, run_id: str) -> str:
        """Generate a unique temp directory path for a run."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dir_name = f"devops_agent_{run_id}_{timestamp}"
        return os.path.join(self.temp_base_dir, dir_name)
    
    def clone_repository(self, repo_url: str, run_id: str) -> Tuple[str, Repo]:
        """
        Clone a repository to a unique temp directory.
        
        Args:
            repo_url: GitHub repository URL
            run_id: Unique run identifier
            
        Returns:
            Tuple of (temp_dir_path, Repo object)
            
        Raises:
            GitCommandError: If cloning fails
            ValueError: If invalid URL
        """
        repo_info = extract_repo_info(repo_url)
        if not repo_info["clone_url"]:
            raise ValueError(f"Invalid repository URL: {repo_url}")
        
        temp_dir = self._generate_temp_dir(run_id)
        
        # Ensure temp directory doesn't exist
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        
        try:
            # Clone using GitPython
            repo = Repo.clone_from(
                repo_info["clone_url"],
                temp_dir,
                depth=1  # Shallow clone for speed
            )
            return temp_dir, repo
        except GitCommandError as e:
            # Cleanup on failure
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise e
    
    def clone_repository_subprocess(self, repo_url: str, run_id: str) -> str:
        """
        Clone a repository using subprocess (alternative method).
        
        Args:
            repo_url: GitHub repository URL
            run_id: Unique run identifier
            
        Returns:
            Path to cloned repository
            
        Raises:
            subprocess.CalledProcessError: If cloning fails
        """
        repo_info = extract_repo_info(repo_url)
        if not repo_info["clone_url"]:
            raise ValueError(f"Invalid repository URL: {repo_url}")
        
        temp_dir = self._generate_temp_dir(run_id)
        
        # Ensure temp directory doesn't exist
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        
        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", repo_info["clone_url"], temp_dir],
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )
            
            if result.returncode != 0:
                raise subprocess.CalledProcessError(
                    result.returncode,
                    result.args,
                    result.stdout,
                    result.stderr
                )
            
            return temp_dir
        except Exception as e:
            # Cleanup on failure
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise e
    
    def create_branch(self, repo: Repo, branch_name: str) -> None:
        """
        Create and checkout a new branch.
        
        Args:
            repo: GitPython Repo object
            branch_name: Name of the branch to create
            
        Raises:
            GitCommandError: If branch creation fails
        """
        # Create and checkout new branch
        repo.git.checkout('-b', branch_name)
    
    def create_branch_subprocess(self, repo_dir: str, branch_name: str) -> None:
        """
        Create and checkout a new branch using subprocess.
        
        Args:
            repo_dir: Path to the repository
            branch_name: Name of the branch to create
            
        Raises:
            subprocess.CalledProcessError: If branch creation fails
        """
        result = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=repo_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                result.args,
                result.stdout,
                result.stderr
            )
    
    def cleanup(self, temp_dir: str) -> None:
        """
        Clean up a temp directory.
        
        Args:
            temp_dir: Path to the temp directory to remove
        """
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def detect_project_type(self, repo_dir: str) -> Tuple[ProjectType, list]:
        """
        Detect the project type based on files in the repository.
        
        Args:
            repo_dir: Path to the repository
            
        Returns:
            Tuple of (ProjectType, list of detected files)
        """
        detected_files = []
        project_type = ProjectType.UNKNOWN
        
        repo_path = Path(repo_dir)
        
        # Check for Python project
        python_indicators = [
            "requirements.txt",
            "pyproject.toml",
            "setup.py",
            "Pipfile",
            "poetry.lock"
        ]
        for indicator in python_indicators:
            if (repo_path / indicator).exists():
                detected_files.append(indicator)
                project_type = ProjectType.PYTHON
        
        # Check for Node.js project
        node_indicators = [
            "package.json",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml"
        ]
        for indicator in node_indicators:
            if (repo_path / indicator).exists():
                detected_files.append(indicator)
                # Node takes precedence if both are found
                project_type = ProjectType.NODE
        
        # If we found Python files but no Node files
        if project_type == ProjectType.UNKNOWN and any(
            (repo_path / f).exists() for f in python_indicators
        ):
            project_type = ProjectType.PYTHON
        
        return project_type, detected_files
    
    def detect_test_setup(self, repo_dir: str, project_type: ProjectType) -> Tuple[bool, Optional[str]]:
        """
        Detect if project has test setup and return the test command.
        
        Args:
            repo_dir: Path to the repository
            project_type: Detected project type
            
        Returns:
            Tuple of (has_tests, test_command)
        """
        repo_path = Path(repo_dir)
        
        if project_type == ProjectType.PYTHON:
            # Check for pytest
            if (repo_path / "pytest.ini").exists() or (repo_path / "pyproject.toml").exists():
                return True, "pytest"
            if (repo_path / "tests").is_dir() or (repo_path / "test").is_dir():
                return True, "pytest"
            return False, None
        
        elif project_type == ProjectType.NODE:
            # Check package.json for test script
            package_json = repo_path / "package.json"
            if package_json.exists():
                import json
                try:
                    with open(package_json) as f:
                        pkg = json.load(f)
                        if "scripts" in pkg and "test" in pkg["scripts"]:
                            return True, "npm test"
                except json.JSONDecodeError:
                    pass
            return False, None
        
        return False, None
    
    def commit_changes(
        self,
        repo: Repo,
        file_path: str,
        bug_type: str,
        line_number: int,
        author_name: Optional[str] = None,
        author_email: Optional[str] = None
    ) -> str:
        """
        Commit changes with [AI-AGENT] prefix.
        
        Commit message format: [AI-AGENT] Fix {BUG_TYPE} in {file} line {line_number}
        
        Args:
            repo: GitPython Repo object
            file_path: Path of the fixed file (relative to repo)
            bug_type: Type of bug (SYNTAX, IMPORT, etc.)
            line_number: Line number where fix was applied
            author_name: Git author name (optional)
            author_email: Git author email (optional)
            
        Returns:
            Commit hash
        """
        from config.settings import get_settings
        settings = get_settings()
        
        # Stage the changed file
        repo.index.add([file_path])
        
        # Build commit message with required prefix
        file_name = os.path.basename(file_path)
        commit_message = f"[AI-AGENT] Fix {bug_type} in {file_name} line {line_number}"
        
        # Set author if provided
        author = None
        if author_name or author_email:
            from git import Actor
            author = Actor(
                author_name or settings.GIT_USER_NAME,
                author_email or settings.GIT_USER_EMAIL
            )
        
        # Commit
        commit = repo.index.commit(commit_message, author=author)
        
        return commit.hexsha
    
    def push_branch(
        self,
        repo: Repo,
        branch_name: str,
        remote_name: str = "origin",
        github_token: Optional[str] = None
    ) -> bool:
        """
        Push branch to remote repository.
        
        Args:
            repo: GitPython Repo object
            branch_name: Branch to push
            remote_name: Remote name (default: origin)
            github_token: GitHub PAT for authentication
            
        Returns:
            True if push successful
        """
        from config.settings import get_settings
        settings = get_settings()
        
        token = github_token or settings.GITHUB_TOKEN
        
        if token:
            # Update remote URL with token for authentication
            remote = repo.remote(remote_name)
            original_url = remote.url
            
            # Insert token into URL: https://TOKEN@github.com/...
            if "github.com" in original_url:
                if original_url.startswith("https://"):
                    auth_url = original_url.replace(
                        "https://github.com",
                        f"https://{token}@github.com"
                    )
                    remote.set_url(auth_url)
        
        try:
            # Push branch
            remote = repo.remote(remote_name)
            remote.push(branch_name)
            return True
        except GitCommandError as e:
            print(f"Push failed: {e}")
            return False
        finally:
            # Restore original URL (remove token from URL)
            if token and "github.com" in original_url:
                remote.set_url(original_url)
    
    def get_commit_count(self, repo: Repo, branch_name: str) -> int:
        """
        Get number of commits on a branch after branching from main.
        
        Args:
            repo: GitPython Repo object
            branch_name: Branch name
            
        Returns:
            Number of commits on the branch
        """
        try:
            # Count commits that are on branch but not on main/master
            main_branch = "main"
            if "master" in [ref.name for ref in repo.heads]:
                main_branch = "master"
            
            commits = list(repo.iter_commits(f"{main_branch}..{branch_name}"))
            return len(commits)
        except Exception:
            return 0


# Singleton instance
git_service = GitService()
