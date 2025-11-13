"""
Platform suggestions for UTM source and medium.
Provides default values when a platform is selected.
"""

PLATFORM_SUGGESTIONS = {
    "Google Ads": {
        "utm_source": "google",
        "utm_medium": "paid_search"
    },
    "Meta": {
        "utm_source": "facebook",
        "utm_medium": "paid_social"
    },
    "Facebook": {
        "utm_source": "facebook",
        "utm_medium": "paid_social"
    },
    "Instagram": {
        "utm_source": "instagram",
        "utm_medium": "paid_social"
    },
    "TikTok": {
        "utm_source": "tiktok",
        "utm_medium": "paid_social"
    },
    "LinkedIn": {
        "utm_source": "linkedin",
        "utm_medium": "paid_social"
    },
    "Email": {
        "utm_source": "mailchimp",
        "utm_medium": "email"
    }
}


def get_platform_suggestion(platform):
    """
    Get suggested utm_source and utm_medium for a given platform.
    
    Args:
        platform (str): Platform name
        
    Returns:
        dict: Dictionary with 'utm_source' and 'utm_medium' keys, or None if not found
    """
    return PLATFORM_SUGGESTIONS.get(platform)

