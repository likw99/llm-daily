from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple


class BaseCollector(ABC):
    """Abstract base class for all data collectors"""
    
    @abstractmethod
    def collect_data(self, **kwargs) -> Dict[str, Any]:
        """
        Collect data from the source
        
        Args:
            **kwargs: Additional parameters for collection
            
        Returns:
            Dict[str, Any]: Collected data
        """
        pass
    
    @abstractmethod
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """
        Format the collected data for LLM consumption
        
        Args:
            data: The collected data
            
        Returns:
            str: Formatted text for LLM input
        """
        pass
    
    def run(self, **kwargs) -> Tuple[str, Dict[str, Any]]:
        """
        Run the full collection and formatting pipeline
        
        Args:
            **kwargs: Additional parameters for collection
            
        Returns:
            Tuple[str, Dict[str, Any]]: Formatted data for LLM and raw data
        """
        try:
            data = self.collect_data(**kwargs)
            formatted_data = self.format_for_llm(data)
            return formatted_data, data
        except Exception as e:
            # Return nothing rather than the error text, so the error is never
            # handed to the LLM as if it were news.
            print(f"Error in {self.__class__.__name__}: {e}")
            return "", {}
