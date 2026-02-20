"""Application settings loaded from environment variables."""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings

# Get the backend directory path for .env file
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # App
    APP_NAME: str = "AI Repository Analyser"
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
    TEMP_REPO_DIR: str = os.path.join(BACKEND_DIR, "temp_repos")
    
    # Groq LLM
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    
    # GitHub Integration
    GITHUB_TOKEN: str = ""  # Personal Access Token for creating PRs
    GIT_USER_NAME: str = "AI Agent"
    GIT_USER_EMAIL: str = "ai-agent@devops.local"
    
    # CI/CD Settings
    CI_TIMEOUT: int = 300  # Max time to wait for CI (seconds)
    AUTO_MERGE_ON_SUCCESS: bool = True  # Auto-merge PR when CI passes
    
    class Config:
        env_file = os.path.join(BACKEND_DIR, ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
