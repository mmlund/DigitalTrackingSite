# Testing Instructions

## Step 1: Start the Flask Server

Open a **new terminal/PowerShell window** and run:

```powershell
cd C:\Users\mmlun\DNStrainer\DNStracking
.\venv\Scripts\Activate.ps1
python app.py
```

Keep this terminal open. You should see:
```
 * Running on http://0.0.0.0:5000
```

## Step 2: Run Tests (in a NEW terminal)

Open a **second terminal/PowerShell window** and run:

```powershell
cd C:\Users\mmlun\DNStrainer\DNStracking
.\venv\Scripts\Activate.ps1
python test_track_endpoint.py
```

## Step 3: Run Simulation Script

In the same second terminal (after tests complete):

```powershell
python scripts/simulate_clicks.py
```

## Step 4: View Dashboard

Open your browser and go to:
```
http://localhost:5000/dashboard
```

## Quick Test with curl

Once the server is running, you can also test manually with curl:

```powershell
curl "http://localhost:5000/track?utm_source=instagram&utm_medium=paid_social&utm_campaign=Summer_Sale_2025&fbclid=IwAR123&campaign_id=123456789"
```

Expected response:
```json
{"status": "ok", "id": "..."}
```

