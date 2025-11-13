"""
Rate limiting module for tracking endpoint.
Limits requests to 20 per second per IP address.
"""

from collections import defaultdict, deque
from datetime import datetime, timedelta
import time

# Store request timestamps per IP
_ip_requests = defaultdict(deque)
# Lock for thread safety (simple implementation)
_request_lock = {}


def is_rate_limited(ip_address, max_requests=20, time_window=1):
    """
    Check if an IP address has exceeded the rate limit.
    
    Args:
        ip_address (str): Client IP address
        max_requests (int): Maximum requests allowed (default: 20)
        time_window (int): Time window in seconds (default: 1 second)
        
    Returns:
        tuple: (is_limited: bool, remaining_requests: int, reset_time: float)
    """
    now = time.time()
    
    # Get request history for this IP
    requests = _ip_requests[ip_address]
    
    # Remove requests older than the time window
    cutoff_time = now - time_window
    while requests and requests[0] < cutoff_time:
        requests.popleft()
    
    # Check if limit exceeded
    if len(requests) >= max_requests:
        # Calculate when the oldest request will expire
        oldest_request = requests[0] if requests else now
        reset_time = oldest_request + time_window
        return True, 0, reset_time
    
    # Add current request
    requests.append(now)
    
    # Calculate remaining requests
    remaining = max_requests - len(requests)
    reset_time = now + time_window
    
    return False, remaining, reset_time


def get_rate_limit_info(ip_address, max_requests=20):
    """Get rate limit information for an IP address."""
    now = time.time()
    requests = _ip_requests[ip_address]
    
    # Remove old requests
    cutoff_time = now - 1  # 1 second window
    while requests and requests[0] < cutoff_time:
        requests.popleft()
    
    remaining = max(0, max_requests - len(requests))
    reset_time = now + 1
    
    return {
        "remaining": remaining,
        "limit": max_requests,
        "reset_time": reset_time
    }

