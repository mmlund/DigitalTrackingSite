
import json
from datetime import datetime, timedelta
from ..database import get_collection

def aggregate_campaign_performance(days=30):
    """
    Aggregate campaign performance data for LLM analysis.
    
    Args:
        days (int): Number of days to look back
        
    Returns:
        dict: Aggregated data summary
    """
    collection = get_collection("raw_events")
    start_date = datetime.utcnow() - timedelta(days=days)
    
    pipeline = [
        {
            "$match": {
                "timestamp": {"$gte": start_date}
            }
        },
        {
            "$group": {
                "_id": {
                    "source": "$utm_source",
                    "campaign": "$utm_campaign",
                    "medium": "$utm_medium"
                },
                "total_clicks": {"$sum": 1},
                "conversions": {
                    "$sum": {
                        "$cond": [{"$eq": ["$event_type", "conversion"]}, 1, 0]
                    }
                },
                "total_revenue": {
                    "$sum": {
                        "$cond": [{"$eq": ["$event_type", "conversion"]}, "$conversion_value", 0]
                    }
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "source": "$_id.source",
                "campaign": "$_id.campaign",
                "medium": "$_id.medium",
                "clicks": "$total_clicks",
                "conversions": "$conversions",
                "revenue": "$total_revenue",
                "conversion_rate": {
                    "$cond": [
                        {"$eq": ["$total_clicks", 0]},
                        0,
                        {"$divide": ["$conversions", "$total_clicks"]}
                    ]
                }
            }
        },
        {
            "$sort": {"revenue": -1}
        }
    ]
    
    results = list(collection.aggregate(pipeline))
    return results

def export_for_llm(output_file="data/llm_analysis_input.json"):
    """
    Export aggregated data to a JSON file for LLM consumption.
    """
    data = aggregate_campaign_performance()
    
    summary = {
        "analysis_date": datetime.utcnow().isoformat(),
        "period_days": 30,
        "total_campaigns": len(data),
        "campaign_data": data
    }
    
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)
        
    return summary
