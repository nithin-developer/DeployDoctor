"""Configuration package."""
import os
from dotenv import load_dotenv

# Load .env file before importing settings
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from .settings import Settings, get_settings
from .database import Base, get_db, engine, async_session_maker

# Export settings instance for backward compatibility with `from config import settings`
settings = get_settings()

__all__ = ["Settings", "get_settings", "Base", "get_db", "engine", "async_session_maker", "settings"]
