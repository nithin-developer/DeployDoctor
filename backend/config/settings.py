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
    
    # ============ CI/CD Agent Settings ============
    
    # GitHub
    GITHUB_TOKEN: str = ""  # Personal Access Token for pushing commits
    GIT_USER_NAME: str = "AI Agent"
    GIT_USER_EMAIL: str = "ai-agent@devops.local"
    
    # Groq LLM
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"  # or mixtral-8x7b-32768, llama2-70b-4096
    
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
    return Settings()
