"""
Git Manager - Handles Git operations for pushing fixes to GitHub
"""
import os
import re
import logging
from datetime import datetime
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class GitManager:
    """Manages Git operations for pushing analysis fixes to GitHub"""
    
    def __init__(self, repo_path: str, github_token: Optional[str] = None):
        self.repo_path = repo_path
        self.github_token = github_token
        self.repo = None
        self._init_repo()
    
    def _init_repo(self):
        """Initialize GitPython repo object"""
        try:
            from git import Repo
            self.repo = Repo(self.repo_path)
        except Exception as e:
            logger.error(f"Failed to initialize git repo: {e}")
            raise
    
    def create_fix_branch(self, team_name: str, team_leader_name: str) -> str:
        """Create a new branch for the fixes using format: TEAM_NAME_LeaderName_AI_Fix"""
        # Sanitize names for branch - replace spaces with underscores, remove special chars
        safe_team = re.sub(r'[^a-zA-Z0-9_]', '_', team_name).upper()
        safe_leader = re.sub(r'[^a-zA-Z0-9_]', '_', team_leader_name)
        
        # Branch name format: TEAM_NAME_LeaderName_AI_Fix
        branch_name = f"{safe_team}_{safe_leader}_AI_Fix"
        
        try:
            # Create and checkout new branch from current HEAD
            self.repo.git.checkout('-b', branch_name)
            logger.info(f"Created branch: {branch_name}")
            return branch_name
        except Exception as e:
            logger.error(f"Failed to create branch: {e}")
            raise
    
    def stage_all_changes(self):
        """Stage all modified files"""
        try:
            self.repo.git.add('-A')
            logger.info("Staged all changes")
        except Exception as e:
            logger.error(f"Failed to stage changes: {e}")
            raise
    
    def commit_changes(self, message: str) -> str:
        """Commit staged changes and return commit SHA"""
        try:
            # Check if there are changes to commit
            if not self.repo.is_dirty() and not self.repo.untracked_files:
                logger.info("No changes to commit")
                return ""
            
            self.repo.git.commit('-m', message)
            commit_sha = self.repo.head.commit.hexsha
            logger.info(f"Committed changes: {commit_sha[:8]}")
            return commit_sha
        except Exception as e:
            logger.error(f"Failed to commit changes: {e}")
            raise
    
    def push_to_remote(self, branch_name: str) -> Tuple[bool, str]:
        """Push branch to remote using GitHub token"""
        if not self.github_token:
            return False, "No GitHub token provided"
        
        try:
            # Get remote URL and modify to include token
            remote = self.repo.remote('origin')
            original_url = remote.url
            
            # Handle different URL formats
            if original_url.startswith('https://'):
                # HTTPS URL - inject token
                auth_url = self._inject_token_to_url(original_url)
            elif original_url.startswith('git@'):
                # SSH URL - convert to HTTPS with token
                auth_url = self._convert_ssh_to_https(original_url)
            else:
                return False, f"Unsupported remote URL format: {original_url}"
            
            # Temporarily set the remote URL with auth
            self.repo.git.remote('set-url', 'origin', auth_url)
            
            try:
                # Push the branch
                self.repo.git.push('--set-upstream', 'origin', branch_name)
                
                # Generate branch URL
                branch_url = self._get_branch_url(original_url, branch_name)
                
                logger.info(f"Pushed branch to: {branch_url}")
                return True, branch_url
            finally:
                # Restore original URL (without token)
                self.repo.git.remote('set-url', 'origin', original_url)
            
        except Exception as e:
            error_msg = str(e)
            # Don't expose token in error message
            if self.github_token and self.github_token in error_msg:
                error_msg = error_msg.replace(self.github_token, '***')
            logger.error(f"Failed to push: {error_msg}")
            return False, f"Push failed: {error_msg}"
    
    def _inject_token_to_url(self, url: str) -> str:
        """Inject GitHub token into HTTPS URL"""
        # https://github.com/user/repo.git -> https://token@github.com/user/repo.git
        if 'github.com' in url:
            return url.replace('https://github.com', f'https://{self.github_token}@github.com')
        return url
    
    def _convert_ssh_to_https(self, ssh_url: str) -> str:
        """Convert SSH URL to HTTPS with token"""
        # git@github.com:user/repo.git -> https://token@github.com/user/repo.git
        match = re.match(r'git@github\.com:(.+)', ssh_url)
        if match:
            path = match.group(1)
            return f'https://{self.github_token}@github.com/{path}'
        return ssh_url
    
    def _get_branch_url(self, original_url: str, branch_name: str) -> str:
        """Generate the GitHub URL for the branch"""
        # Extract repo path from URL
        if original_url.startswith('https://github.com/'):
            repo_path = original_url[19:].replace('.git', '')
        elif original_url.startswith('git@github.com:'):
            repo_path = original_url[15:].replace('.git', '')
        else:
            repo_path = original_url
        
        return f"https://github.com/{repo_path}/tree/{branch_name}"
    
    def get_current_commit_sha(self) -> str:
        """Get the current commit SHA"""
        try:
            return self.repo.head.commit.hexsha
        except Exception:
            return ""
    
    def get_diff_summary(self) -> dict:
        """Get a summary of changes"""
        try:
            modified = [item.a_path for item in self.repo.index.diff(None)]
            staged = [item.a_path for item in self.repo.index.diff('HEAD')]
            untracked = self.repo.untracked_files
            
            return {
                "modified": modified,
                "staged": staged,
                "untracked": list(untracked),
                "total_changes": len(modified) + len(staged) + len(untracked)
            }
        except Exception as e:
            logger.warning(f"Could not get diff summary: {e}")
            return {"modified": [], "staged": [], "untracked": [], "total_changes": 0}
    
    def cleanup(self):
        """Cleanup and reset repo state if needed"""
        try:
            if self.repo.is_dirty():
                self.repo.git.checkout('--', '.')
            # Return to original branch
            self.repo.git.checkout('-')
        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")
