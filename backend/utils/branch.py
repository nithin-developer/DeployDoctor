import re


def generate_branch_name(team_name: str, leader_name: str) -> str:
    """
    Generate branch name following EXACT format requirement:
    TEAM_NAME_LEADER_NAME_AI_Fix
    
    Rules:
    - UPPERCASE
    - Spaces → underscores
    - End with _AI_Fix
    - No special characters (only alphanumeric and underscores)
    """
    # Combine team and leader names
    name = f"{team_name}_{leader_name}"
    
    # Convert to uppercase
    name = name.upper()
    
    # Replace spaces with underscores
    name = name.replace(" ", "_")
    
    # Remove any special characters (keep only alphanumeric and underscores)
    name = re.sub(r'[^A-Z0-9_]', '', name)
    
    # Remove multiple consecutive underscores
    name = re.sub(r'_+', '_', name)
    
    # Remove leading/trailing underscores
    name = name.strip('_')
    
    # Append _AI_Fix suffix
    branch_name = f"{name}_AI_Fix"
    
    return branch_name


def validate_github_url(url: str) -> bool:
    """Check if URL is a valid GitHub repository URL."""
    pattern = r'^https?://github\.com/[\w\-]+/[\w\-\.]+(?:\.git)?/?$'
    return bool(re.match(pattern, url.strip()))


def extract_repo_info(repo_url: str) -> dict:
    """Extract owner and repo name from GitHub URL."""
    url = repo_url.strip().rstrip('/')
    if url.endswith('.git'):
        url = url[:-4]
    
    # Pattern: https://github.com/owner/repo
    pattern = r'https?://github\.com/([\w\-]+)/([\w\-\.]+)'
    match = re.match(pattern, url)
    
    if match:
        return {
            "owner": match.group(1),
            "repo": match.group(2),
            "clone_url": f"https://github.com/{match.group(1)}/{match.group(2)}.git"
        }
    
    return {"owner": None, "repo": None, "clone_url": None}
