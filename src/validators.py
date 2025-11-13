"""
Validation functions for URL generator inputs.
"""

import re
from urllib.parse import quote


def validate_utm_source(utm_source):
    """
    Validate UTM source value.
    
    Args:
        utm_source (str): UTM source value
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not utm_source or not utm_source.strip():
        return False, "UTM source is required"
    
    if len(utm_source) > 100:
        return False, "UTM source must be 100 characters or less"
    
    # Allow alphanumeric, hyphens, underscores, and dots
    if not re.match(r'^[a-zA-Z0-9._-]+$', utm_source):
        return False, "UTM source contains invalid characters"
    
    return True, None


def validate_utm_medium(utm_medium):
    """
    Validate UTM medium value.
    
    Args:
        utm_medium (str): UTM medium value
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not utm_medium or not utm_medium.strip():
        return False, "UTM medium is required"
    
    return True, None


def validate_campaign_name(campaign_name, use_dynamic):
    """
    Validate campaign name.
    
    Args:
        campaign_name (str): Campaign name
        use_dynamic (bool): Whether dynamic placeholders are used
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if use_dynamic:
        # Dynamic mode - campaign name is optional
        return True, None
    
    # Static mode - campaign name should be provided, but we'll default to "unknown"
    return True, None


def validate_ad_name(ad_name, use_dynamic):
    """
    Validate ad name.
    
    Args:
        ad_name (str): Ad name
        use_dynamic (bool): Whether dynamic placeholders are used
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if use_dynamic:
        # Dynamic mode - ad name is optional
        return True, None
    
    # Static mode - ad name should be provided, but we'll default to "unknown"
    return True, None


def sanitize_parameter_value(value):
    """
    Sanitize parameter value for URL encoding.
    Replace spaces with underscores and encode special characters.
    
    Args:
        value (str): Parameter value
        
    Returns:
        str: Sanitized and URL-encoded value
    """
    if not value:
        return ""
    
    # Replace spaces with underscores
    value = value.strip().replace(" ", "_")
    
    # URL encode
    return quote(value, safe='')


def validate_all_inputs(utm_source, utm_medium, campaign_name, ad_name, adset_name, use_dynamic):
    """
    Validate all form inputs.
    
    Args:
        utm_source (str): UTM source
        utm_medium (str): UTM medium
        campaign_name (str): Campaign name
        ad_name (str): Ad name
        adset_name (str): Ad set name
        use_dynamic (bool): Whether to use dynamic placeholders
        
    Returns:
        tuple: (is_valid, errors_dict)
    """
    errors = {}
    
    # Validate required fields
    is_valid, error = validate_utm_source(utm_source)
    if not is_valid:
        errors["utm_source"] = error
    
    is_valid, error = validate_utm_medium(utm_medium)
    if not is_valid:
        errors["utm_medium"] = error
    
    return len(errors) == 0, errors

