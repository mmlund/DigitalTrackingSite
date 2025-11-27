from abc import ABC, abstractmethod
from typing import Dict, Any, List

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def generate_text(self, prompt: str, system_prompt: str = None, **kwargs) -> str:
        """Generate text from a prompt."""
        pass
    
    @abstractmethod
    def analyze_data(self, data: Dict[str, Any], query: str, **kwargs) -> str:
        """Analyze structured data based on a query."""
        pass

class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing and development."""
    
    def generate_text(self, prompt: str, system_prompt: str = None, **kwargs) -> str:
        return f"Mock response to: {prompt[:50]}..."
    
    def analyze_data(self, data: Dict[str, Any], query: str, **kwargs) -> str:
        return f"Based on the data ({len(data)} items), the answer to '{query}' is: Trends look positive."
