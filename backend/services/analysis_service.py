"""
Repository Analysis Service
"""
from typing import Dict, Any
from models import AnalysisRequest, AnalysisResult
from agents.orchestrator_agent import OrchestratorAgent


class AnalysisService:
    """Service for handling repository analysis"""
    
    def __init__(self):
        self.active_analyses: Dict[str, Dict[str, Any]] = {}
    
    async def analyze_repository(self, request: AnalysisRequest, analysis_id: str) -> AnalysisResult:
        """Perform repository analysis"""
        
        def progress_callback(status: str, progress: int, message: str):
            self.active_analyses[analysis_id] = {
                "status": status,
                "progress": progress,
                "message": message
            }
        
        # Initialize progress
        self.active_analyses[analysis_id] = {
            "status": "starting",
            "progress": 0,
            "message": "Initializing analysis..."
        }
        
        # Create orchestrator with progress callback
        orchestrator = OrchestratorAgent(progress_callback=progress_callback)
        
        # Execute analysis
        context = {"request": request}
        result = await orchestrator.execute(context)
        
        return result.get("result")
    
    def get_analysis_status(self, analysis_id: str) -> Dict[str, Any]:
        """Get the status of an ongoing analysis"""
        return self.active_analyses.get(analysis_id, {
            "status": "not_found",
            "progress": 0,
            "message": "Analysis not found"
        })
    
    def cleanup_analysis(self, analysis_id: str):
        """Clean up analysis data"""
        if analysis_id in self.active_analyses:
            del self.active_analyses[analysis_id]


# Global service instance
analysis_service = AnalysisService()
