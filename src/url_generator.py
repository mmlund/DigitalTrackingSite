"""
URL generator for marketing tracking URLs.
Builds URLs with UTM parameters only.
"""

from urllib.parse import urlencode
from .config import BASE_URL
from .validators import sanitize_parameter_value


def build_tracking_url(utm_source, utm_medium, campaign_name=None, ad_name=None, 
                      adset_name=None, use_dynamic_placeholders=False):
    """
    Build a tracking URL with UTM parameters.
    
    Args:
        utm_source (str): UTM source (required)
        utm_medium (str): UTM medium (required)
        campaign_name (str): Campaign name (optional)
        ad_name (str): Ad name (optional)
        adset_name (str): Ad set name (optional, for utm_term)
        use_dynamic_placeholders (bool): If True, use {{placeholders}}, else use static values
        
    Returns:
        str: Complete tracking URL
    """
    params = {}
    
    # Required parameters
    params["utm_source"] = sanitize_parameter_value(utm_source)
    params["utm_medium"] = sanitize_parameter_value(utm_medium)
    
    # Campaign parameter (utm_campaign)
    if use_dynamic_placeholders:
        if campaign_name:
            params["utm_campaign"] = "{{campaign.name}}"
        # If no campaign name but dynamic, still include placeholder
        else:
            params["utm_campaign"] = "{{campaign.name}}"
    else:
        # Static mode - use provided value or "unknown"
        campaign_value = campaign_name.strip() if campaign_name and campaign_name.strip() else "unknown"
        params["utm_campaign"] = sanitize_parameter_value(campaign_value)
    
    # Content parameter (utm_content) - maps to ad name
    if use_dynamic_placeholders:
        if ad_name:
            params["utm_content"] = "{{ad.name}}"
        # If no ad name but dynamic, still include placeholder
        else:
            params["utm_content"] = "{{ad.name}}"
    else:
        # Static mode - use provided value or "unknown"
        ad_value = ad_name.strip() if ad_name and ad_name.strip() else "unknown"
        params["utm_content"] = sanitize_parameter_value(ad_value)
    
    # Term parameter (utm_term) - maps to adset name (optional)
    if adset_name and adset_name.strip():
        if use_dynamic_placeholders:
            params["utm_term"] = "{{adset.name}}"
        else:
            params["utm_term"] = sanitize_parameter_value(adset_name)
    # If no adset name, omit utm_term entirely
    
    # Build URL
    query_string = urlencode(params)
    full_url = f"{BASE_URL}?{query_string}"
    
    return full_url


def generate_url_data(platform, utm_source, utm_medium, campaign_name=None, 
                     ad_name=None, adset_name=None, use_dynamic_placeholders=False):
    """
    Generate URL and return data structure for storage.
    
    Args:
        platform (str): Platform name
        utm_source (str): UTM source
        utm_medium (str): UTM medium
        campaign_name (str): Campaign name
        ad_name (str): Ad name
        adset_name (str): Ad set name
        use_dynamic_placeholders (bool): Whether to use dynamic placeholders
        
    Returns:
        dict: Dictionary with URL and metadata
    """
    import uuid
    from datetime import datetime
    
    generated_url = build_tracking_url(
        utm_source=utm_source,
        utm_medium=utm_medium,
        campaign_name=campaign_name,
        ad_name=ad_name,
        adset_name=adset_name,
        use_dynamic_placeholders=use_dynamic_placeholders
    )
    
    return {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "platform": platform,
        "utm_source": utm_source,
        "utm_medium": utm_medium,
        "campaign_name": campaign_name or "",
        "ad_name": ad_name or "",
        "adset_name": adset_name or "",
        "use_dynamic_placeholders": use_dynamic_placeholders,
        "generated_url": generated_url
    }

