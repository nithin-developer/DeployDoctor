import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    TEMP_REPO_DIR: str = os.path.join(os.path.dirname(__file__), "temp_repos")
    
settings = Settings()
