# MongoDB Atlas Setup Instructions

## Step 1: Create .env File

Create a `.env` file in the project root directory with the following content:

```env
# MongoDB Atlas Configuration
# IMPORTANT: Replace <db_password> with your actual database password
MONGODB_URI=mongodb+srv://mmlund_db_user:<db_password>@dnstrainerdb.miec9sn.mongodb.net/?appName=DNStrainerDB
MONGODB_DB_NAME=dns_tracking

# Test Mode Configuration
TEST_MODE=True
```

**Important:** Replace `<db_password>` with your actual MongoDB Atlas database user password.

## Step 2: Test Connection

Run the test script to verify your MongoDB connection:

```bash
python test_mongodb_connection.py
```

If successful, you should see:
```
✅ Successfully connected to MongoDB Atlas
📊 Database: dns_tracking
📁 Collections: []
✅ Indexes created successfully!
```

## Troubleshooting

### Connection Failed

1. **Check Password**: Make sure you replaced `<db_password>` with your actual password in the `.env` file
2. **IP Whitelist**: Verify your IP address is whitelisted in MongoDB Atlas Network Access
3. **Database User**: Confirm your database user has read/write permissions

### Common Errors

- `Authentication failed`: Check username/password in connection string
- `IP not whitelisted`: Add your IP in MongoDB Atlas → Network Access
- `Connection timeout`: Check firewall/network settings

## Next Steps

Once the connection test passes, you're ready to implement Phase 2 features:
- `/track` endpoint
- Event storage
- Dashboard

