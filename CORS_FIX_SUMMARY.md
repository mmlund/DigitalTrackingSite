# CORS Issue Resolution

## Problems Identified

### 1. **Root Cause: Relative vs Absolute URL**
The `tracker.js` script was using a **relative endpoint** (`/track`), which meant:
- When loaded on `dnstrainer.com`, it tried to POST to `https://dnstrainer.com/track` ❌
- Should have been POSTing to `https://dnstracking.onrender.com/track` ✅

This is why you saw the CORS error - the browser was making a cross-origin request from `dnstrainer.com` to `dnstracking.onrender.com`, but the tracker wasn't configured correctly.

### 2. **Incomplete CORS Configuration**
The CORS config had the right origins listed, but wasn't explicitly defining:
- Allowed methods (GET, POST, OPTIONS)
- Allowed headers (Content-Type)
- Preflight handling

## Fixes Applied

### Fix #1: Updated `tracker.js`
**File**: `static/js/tracker.js`

**Changed**:
```javascript
// Before
endpoint: '/track',

// After
endpoint: 'https://dnstracking.onrender.com/track',
```

Now the tracker will correctly send events to the Render deployment, regardless of which domain the script is loaded from.

### Fix #2: Enhanced CORS Configuration
**File**: `app.py`

**Changes**:
- Explicitly defined allowed methods: `["GET", "POST", "OPTIONS"]`
- Explicitly defined allowed headers: `["Content-Type"]`
- Set `supports_credentials: False` (we're not using credentials)
- Kept the regex pattern for subdomain matching: `re.compile(r"^https://.*\.dnstrainer\.com$")`

## How to Use

### On Your Website (`dnstrainer.com` or `booking.dnstrainer.com`)

Add this script tag to your HTML:

```html
<script src ="https://dnstracking.onrender.com/static/js/tracker.js"></script>
```

The script will automatically:
1. Track page views on load
2. Track clicks on links, buttons, and elements with class `.cta`
3. Send events to `https://dnstracking.onrender.com/track`

### Required URL Parameters

For tracking to work, your landing pages must have UTM parameters:
- `utm_source` (required)
- `utm_medium` (required)
- `utm_campaign` (required)
- `utm_content` (optional)
- `utm_term` (optional)

Example URL:
```
https://dnstrainer.com?utm_source=google&utm_medium=cpc&utm_campaign=summer_sale
```

## Testing After Deployment

1. **Wait for Render to deploy** (check your Render dashboard)
2. **Open your website** (`dnstrainer.com`) with UTM parameters
3. **Check browser console** - you should see NO CORS errors
4. **Verify in MongoDB** - events should be recorded

## About the 404 Errors

The 404 errors for `/css/support_parent.css` and `/js/lkk_ch.js` are **not** from your tracking system. These are likely:
- Browser extensions trying to inject files
- External analytics/chat widgets
- Old cached references

You can safely ignore these unless they're causing functional issues.

## Domain Configuration

Your current setup:
- **Render Service Name**: `dnstracking` (from `render.yaml`)
- **Render URL**: `https://dnstracking.onrender.com`
- **Client Websites**: `dnstrainer.com`, `booking.dnstrainer.com`, and any `*.dnstrainer.com` subdomain

All are now properly configured for CORS.
