# Quick Start Guide - Testing Phase 2

## ✅ Dependencies Installed

All required packages are now installed in your virtual environment:
- Flask
- pymongo (MongoDB driver)
- python-dotenv
- requests

## 🚀 How to Test

### Step 1: Start the Flask Server

**Open a terminal/PowerShell window** and run:

```powershell
cd C:\Users\mmlun\DNStrainer\DNStracking
.\venv\Scripts\Activate.ps1
python app.py
```

You should see:
```
 * Running on http://0.0.0.0:5000
 * Running on http://127.0.0.1:5000
```

**Keep this terminal window open!**

### Step 2: Run Tests (in a NEW terminal)

**Open a SECOND terminal/PowerShell window** and run:

```powershell
cd C:\Users\mmlun\DNStrainer\DNStracking
.\venv\Scripts\Activate.ps1
python test_track_endpoint.py
```

This will test:
- ✅ Instagram event tracking
- ✅ Google Ads event tracking  
- ✅ POST requests with JSON
- ✅ Validation (missing parameters)
- ✅ TikTok Ads tracking

### Step 3: Run Simulation

In the same second terminal (after tests complete):

```powershell
python scripts/simulate_clicks.py
```

This will:
- Generate 50 events over 2 weeks
- Send them to `/track` endpoint
- Show progress for each event

### Step 4: View Dashboard

Open your browser:
```
http://localhost:5000/dashboard
```

You should see:
- All tracked events
- Filters (campaign_id, utm_source, date range)
- Real-time updates (auto-refreshes every 5 seconds)
- Platform badges
- Pagination

## 🧪 Quick Manual Test

Once the server is running, you can also test manually with curl:

```powershell
curl "http://localhost:5000/track?utm_source=instagram&utm_medium=paid_social&utm_campaign=Summer_Sale_2025&fbclid=IwAR123&campaign_id=123456789"
```

Expected response:
```json
{"status": "ok", "id": "..."}
```

## 📋 What's Been Implemented

✅ `/track` endpoint (GET & POST)
✅ MongoDB Atlas integration
✅ Rate limiting (20 req/sec per IP)
✅ Session management (60-minute timeout)
✅ Platform auto-detection
✅ Validation (required UTMs)
✅ Test script (`test_track_endpoint.py`)
✅ Simulation script (`scripts/simulate_clicks.py`)
✅ Dashboard with filters and real-time updates

## 🐛 Troubleshooting

**Server won't start?**
- Make sure you're in the virtual environment: `.\venv\Scripts\Activate.ps1`
- Check MongoDB connection: `python test_mongodb_connection.py`
- Check `.env` file has correct MongoDB URI with password

**Tests fail?**
- Make sure server is running first
- Check server terminal for error messages
- Verify MongoDB connection is working

**Dashboard shows no data?**
- Run the simulation script to populate test data
- Check filters aren't too restrictive
- Verify events were stored in MongoDB

