"""
Base Agent - Abstract base class for all agents in the multi-agent system.

All agents inherit from this class and implement the execute() method.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from config.settings import get_settings

settings = get_settings()


class AgentStatus(str, Enum):
    """Status of an agent execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class AgentResult:
    """Result from an agent execution."""
    agent_name: str
    status: AgentStatus
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict:
        return {
            "agent_name": self.agent_name,
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "duration_seconds": round(self.duration_seconds, 2),
            "timestamp": self.timestamp.isoformat()
        }


class BaseAgent(ABC):
    """
    Base class for all agents in the CI/CD healing system.
    
    Each agent is responsible for a specific task:
    - SandboxExecutorAgent: Runs code in Docker sandbox
    - ErrorParserAgent: Parses errors from output
    - CodeFixerAgent: Generates code fixes using LLM
    - TestRunnerAgent: Runs tests
    - CIMonitorAgent: Monitors CI/CD pipeline
    - OrchestratorAgent: Coordinates all agents
    """
    
    def __init__(
        self, 
        name: str, 
        description: str,
        use_llm: bool = True
    ):
        """
        Initialize the agent.
        
        Args:
            name: Human-readable name of the agent
            description: What this agent does
            use_llm: Whether this agent needs LLM access
        """
        self.name = name
        self.description = description
        self.use_llm = use_llm
        self._llm: Optional[ChatGroq] = None
        self.progress_callback: Optional[Callable[[str, int, str], None]] = None
    
    @property
    def llm(self) -> ChatGroq:
        """Lazy-load LLM instance."""
        if self._llm is None and self.use_llm:
            self._llm = ChatGroq(
                api_key=settings.GROQ_API_KEY,
                model=settings.GROQ_MODEL,
                temperature=0.1  # Low temperature for consistent fixes
            )
        return self._llm
    
    def set_progress_callback(self, callback: Callable[[str, int, str], None]):
        """Set callback for progress reporting."""
        self.progress_callback = callback
    
    def report_progress(self, status: str, progress: int, message: str):
        """Report progress to callback if available."""
        if self.progress_callback:
            self.progress_callback(status, progress, message)
    
    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        return f"You are {self.name}. {self.description}"
    
    async def invoke_llm(
        self, 
        system_prompt: str, 
        user_prompt: str
    ) -> str:
        """
        Invoke the LLM with system and user prompts.
        
        Args:
            system_prompt: The system prompt
            user_prompt: The user prompt
            
        Returns:
            LLM response as string
        """
        if not self.use_llm:
            raise RuntimeError(f"Agent {self.name} does not use LLM")
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        return response.content
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        Execute the agent's task.
        
        Args:
            context: Dictionary with execution context including:
                - repo_path: Path to the repository
                - project_type: Type of project (python, node, etc.)
                - Other agent-specific parameters
                
        Returns:
            AgentResult with status and data
        """
        pass
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name}>"
