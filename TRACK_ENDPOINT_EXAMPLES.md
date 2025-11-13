# /track Endpoint Examples

## Basic Usage

The `/track` endpoint accepts both GET and POST requests and captures all query parameters.

### Example: GET Request

```bash
curl "http://localhost:5000/track?utm_source=instagram&utm_medium=paid_social&utm_campaign=Summer_Sale_2025&utm_content=Video_Ad_1&fbclid=IwAR1xYzAbC123&campaign_id=123456789"
```

### Example: POST Request (JSON)

```bash
curl -X POST http://localhost:5000/track \
  -H "Content-Type: application/json" \
  -d '{
    "utm_source": "instagram",
    "utm_medium": "paid_social",
    "utm_campaign": "Summer_Sale_2025",
    "utm_content": "Video_Ad_1",
    "fbclid": "IwAR1xYzAbC123",
    "campaign_id": "123456789"
  }'
```

### Example: POST Request (Form Data)

```bash
curl -X POST http://localhost:5000/track \
  -d "utm_source=instagram" \
  -d "utm_medium=paid_social" \
  -d "utm_campaign=Summer_Sale_2025" \
  -d "utm_content=Video_Ad_1" \
  -d "fbclid=IwAR1xYzAbC123" \
  -d "campaign_id=123456789"
```

## Required Parameters

The following UTM parameters are **required**:
- `utm_source`
- `utm_medium`
- `utm_campaign`

## Response Format

### Success Response

```json
{
  "status": "ok",
  "id": "507f1f77bcf86cd799439011"
}
```

### Error Response (Validation)

```json
{
  "status": "error",
  "message": "Missing required UTM parameters: utm_source, utm_medium"
}
```

### Error Response (Rate Limit)

```json
{
  "status": "error",
  "message": "Rate limit exceeded. Maximum 20 requests per second.",
  "retry_after": 1234567890.123
}
```

## Platform-Specific Examples

### Google Ads

```bash
curl "http://localhost:5000/track?utm_source=google&utm_medium=paid_search&utm_campaign=Summer_Sale&utm_content=Search_Ad_1&utm_term=keyword&gclid=EAlalQobChMI5YyF8Y6AhUJ&campaign_id=123456789"
```

### Meta/Facebook

```bash
curl "http://localhost:5000/track?utm_source=facebook&utm_medium=paid_social&utm_campaign=Summer_Sale&utm_content=Video_Ad&fbclid=IwAR1xYzAbC123&campaign_id=987654321&adset_id=456789012&ad_id=789012345&placement=feed"
```

### Instagram

```bash
curl "http://localhost:5000/track?utm_source=instagram&utm_medium=paid_social&utm_campaign=Summer_Sale&utm_content=Story_Ad&fbclid=IwAR1xYzAbC123&igshid=MzRIODBIN123&campaign_id=111222333&adset_id=444555666&ad_id=777888999&placement=stories"
```

### TikTok

```bash
curl "http://localhost:5000/track?utm_source=tiktok&utm_medium=paid_social&utm_campaign=Summer_Sale&utm_content=Video_Ad&ttclid=Cj0KCQiA123&campaign_id=555666777"
```

### Microsoft Ads

```bash
curl "http://localhost:5000/track?utm_source=bing&utm_medium=paid_search&utm_campaign=Summer_Sale&utm_content=Search_Ad&msclkid=abc123def456&campaign_id=999888777"
```

## Testing

Use the simulation script to generate test events:

```bash
python scripts/simulate_clicks.py
```

This will generate 50 events over a 2-week period and send them to the `/track` endpoint.

