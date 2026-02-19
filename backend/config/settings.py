import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # App
    APP_NAME: str = "DevOps CI/CD Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/devops_agent"
    
    # JWT
    JWT_SECRET: str = "change-this-secret-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    FRONTEND_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    
    # Cookie
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    
    # Temp directory for cloned repos
    TEMP_DIR: str = ""  # Empty = use system temp
    
    # Temp repo dir for analysis agent (auto-computed if empty)
    TEMP_REPO_DIR: str = ""
    
    # ============ CI/CD Agent Settings ============
    
    # GitHub
    GITHUB_TOKEN: str = ""  # Personal Access Token for pushing commits
    GIT_USER_NAME: str = "AI Agent"
    GIT_USER_EMAIL: str = "ai-agent@devops.local"
    
    # Groq LLM
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    
    # Docker
    DOCKER_MEMORY_LIMIT: str = "512m"
    DOCKER_CPU_LIMIT: float = 1.0
    DOCKER_TIMEOUT: int = 300  # 5 minutes
    PYTHON_IMAGE: str = "python:3.10-slim"
    NODE_IMAGE: str = "node:18-slim"
    
    # Agent
    MAX_RETRIES: int = 5
    SPEED_BONUS_THRESHOLD: int = 300  # 5 minutes for +10 bonus
    COMMIT_PENALTY_THRESHOLD: int = 20  # -2 per commit over this
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Allow extra fields in .env


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    s = Settings()
    # Auto-compute TEMP_REPO_DIR if not set
    if not s.TEMP_REPO_DIR:
        s.TEMP_REPO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "temp_repos")
    return s
