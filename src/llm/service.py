from .provider import LLMProvider, MockLLMProvider
from typing import Dict, Any

class LLMService:
    """Service for handling LLM operations."""
    
    def __init__(self, provider: LLMProvider = None):
        self.provider = provider or MockLLMProvider()
    
    def analyze_marketing_data(self, data: Dict[str, Any], query: str) -> str:
        """
        Analyze marketing data using the LLM.
        
        Args:
            data: Dictionary containing marketing metrics/events
            query: User's question about the data
            
        Returns:
            Analysis string
        """
        # Here we could pre-process data, summarize it if it's too large, etc.
        return self.provider.analyze_data(data, query)

# Singleton instance
llm_service = LLMService()
