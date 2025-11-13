# Test Mode Guide

## Quick Start

### Enable Test Mode

**Option 1: Environment Variable (Windows PowerShell)**
```powershell
$env:TEST_MODE="True"
python app.py
```

**Option 2: Environment Variable (Windows CMD)**
```cmd
set TEST_MODE=True
python app.py
```

**Option 3: Environment Variable (Mac/Linux)**
```bash
export TEST_MODE=True
python app.py
```

**Option 4: Create .env file** (requires python-dotenv - optional)
Create a `.env` file in the project root:
```
TEST_MODE=True
```

### Disable Test Mode

Simply unset the environment variable or set it to `False`:
```powershell
$env:TEST_MODE="False"
# or
Remove-Item Env:\TEST_MODE
```

## What Test Mode Does

### 1. Fixes Jinja2 Template Error
- In test mode, the template uses actual example values instead of `{{campaign.name}}`
- This prevents the "campaign is undefined" error

### 2. Shows Example Values
- Placeholder labels show: `(Summer_Sale_2025, Video_Ad_1, etc.)`
- Instead of: `({{campaign.name}}, {{ad.name}}, etc.)`

### 3. Enables Preview Mode
- "Preview Full URL" button appears after generating a URL
- Shows what the complete URL would look like when it arrives at your site
- Includes platform-specific parameters:
  - Google Ads: `gclid`, `campaign_id`
  - Meta/Facebook: `fbclid`, `campaign_id`, `adset_id`, `ad_id`, `placement`
  - Instagram: `fbclid`, `igshid`, `campaign_id`, `adset_id`, `ad_id`, `placement`
  - TikTok: `ttclid`, `campaign_id`
  - Microsoft Ads: `msclkid`, `campaign_id`

### 4. Test Mode Banner
- Yellow banner at top of page indicates test mode is active
- Helps prevent confusion between test and production

## Example: Preview Full URL

**Generated URL (UTM Only):**
```
http://dnstrainer.com/landing?utm_source=instagram&utm_medium=paid_social&utm_campaign={{campaign.name}}&utm_content={{ad.name}}
```

**Preview Full URL (with platform parameters):**
```
http://dnstrainer.com/landing?utm_source=instagram&utm_medium=paid_social&utm_campaign={{campaign.name}}&utm_content={{ad.name}}&fbclid=IwAR1xYzAbC123def456ghi789&igshid=MzRIODBIN123456789&campaign_id=111222333&adset_id=444555666&ad_id=777888999&placement=stories
```

## Mock Data Structure

Mock data is stored in `data/mock_data.json` and includes:

- **Test Scenarios**: Pre-configured test data for each platform
- **Example Placeholders**: Sample values for campaign.name, ad.name, adset.name
- **Parameter Formats**: Documentation of expected parameter formats

You can edit `data/mock_data.json` to customize test scenarios.

## Use Cases

1. **Development**: Test your URL generator without real campaigns
2. **Phase 2 Preparation**: Understand what parameters will arrive at your site
3. **Documentation**: Show stakeholders what tracking URLs look like
4. **Testing**: Validate your parameter capture system before going live

## Switching Between Modes

**For Development/Testing:**
```powershell
$env:TEST_MODE="True"
python app.py
```

**For Production URL Generation:**
```powershell
$env:TEST_MODE="False"
# or simply don't set it
python app.py
```

The system automatically adapts based on the `TEST_MODE` setting.

