"""
Base Agent class for the multi-agent system
"""
from abc import ABC, abstractmethod
from typing import Any, Dict
from langchain_groq import ChatGroq
from config import settings


class BaseAgent(ABC):
    """Base class for all agents in the system"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.llm = ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
            temperature=0.1
        )
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's task"""
        pass
    
    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent"""
        return f"You are {self.name}. {self.description}"
