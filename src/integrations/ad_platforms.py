from abc import ABC, abstractmethod
from datetime import datetime, timedelta

class AdPlatformService(ABC):
    """Abstract base class for ad platform integrations."""
    
    @abstractmethod
    def authenticate(self):
        """Authenticate with the platform API."""
        pass
    
    @abstractmethod
    def get_campaign_performance(self, start_date, end_date):
        """
        Fetch campaign performance data.
        
        Args:
            start_date (datetime): Start date
            end_date (datetime): End date
            
        Returns:
            list: List of campaign performance records
        """
        pass
    
    @abstractmethod
    def get_ad_performance(self, start_date, end_date):
        """
        Fetch ad performance data.
        
        Args:
            start_date (datetime): Start date
            end_date (datetime): End date
            
        Returns:
            list: List of ad performance records
        """
        pass
