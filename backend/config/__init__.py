"""
Config package - Exports settings instance for backward compatibility.
Agents import using `from config import settings`
"""
from config.settings import get_settings

settings = get_settings()
