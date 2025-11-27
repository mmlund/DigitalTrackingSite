This repository contains the files for backend tracking for varions websites. Although the first installation os for the sie dnstrainer.com and scnadinavianclinic.com it will be set-up to manage the expansion to handle back-end tracking for several websites.

The general idea is to first generate tracking urls for all marketing avenues i.e. Google ads, FB, Instagram, Tik-Tok, Youtube, emails, social media posts etc. This is the first step: DNS tracking URL generator.

All entries, home page and landing pages will capture these urls and the information contained in them (the tracking information) and store in a database (MongoDB JSON)

This is done trough calling an API that we will create in this project. The API call will be triggered by EACH WEBSITE.

We will also collect additional data on the usage from the website i.e. time spent on page, number of pages visited, scroll depth, CTA etc. This data will be stored in a database (MongoDB JSON)that we will connect to in this project. Data will also be stored for conversions i.e. appointments booked, value of sale etc.as well as customer information (email, phone number, name etc.).

In a seperate, but connected database we will collect information abouth the particular environment of relevance to the marketing for each company.This will include information such as competitors, competitors actions, market trends, customer feedback, social media activity etc. This data will be collected from public sources and APIs as well as scraping of social media platforms.

All this data collected will be made available to the user for tracking and analysis using an LLM (Large Language Model). The user will then be able to ask any questions related to the marketing for this company such as trends, success rate of campaigns, types of users, customer journey etc., using the LLM and the data.
The LLm will have access to tools such as calculator, code-generator, charting capabilities etc. The system will have a dashbord for a quick overview of the marketing for the company.

In a later step this will be connected to a campaign generator that will generate suggestions for newletters, ads, social media content, videos etc based on the data collected. The system will eventually be able to generate and implement suggestions for marketing campaigns and even post this automatically after review by the user.

The LLM will have acces to the data collected as well asThe flow works as follows:
1. NOW-Generate urls for marketing campaigns
2. NOW -Collect and process urls when people land on pages
3. NOW -Collect more data on usage from the website
4. NOW -Collect CTA, $ value and other data as well as customer information (email, phone number, name etc.)
5. NOW Store collected data in an optimal format - this may be RAG type
6. NOW Enable dashboard for quick overview of marketing for the company
7. NOWEnable LLM for analysis of marketing data
8. LATER -enable campaign generator for suggestions for newletters, ads, social media content, videos etc based on the data collectedEna
9. LATER -Automate postings and campaingns
10. LATER -measure performance of marketing campaigns
11. LATER -Self-reflectiona and improvement of marketing campaigns

ABOUT DEVELOPMENT

The system will be developed using Python and Flask. The database will be MongoDB. The LLM SHOULD BE FLEXIBLE AND NOT HARD CODED TO A SPECIFIC LLM. 
The system will be hosted on Render and will be accessible from the website. 
To ensure a smooth deployment prioritize simplicity in the code and deployment process. I am inexperiences in this aspects and not a technician. I need detailed instructions and explanations. 
Ask questions if something is not clear in particular before critical operations are performed.

tHE SYSTEM WILL BE HOSTED ON RENDER AND WILL BE ACCESSIBLE FROM THE WEBSITE

# DNS Tracking URL Generator

Phase 1 of the DNS Marketing Tracking System - URL Generator Module

## Overview

This system generates marketing tracking URLs with UTM parameters for campaigns across multiple platforms (Google Ads, Meta, Facebook, Instagram, TikTok, LinkedIn, etc.).

## Features

- **Platform Selection**: Choose from Google Ads, Meta, Facebook, Instagram, TikTok, LinkedIn, Email, or Other
- **UTM Source Management**: Hierarchical dropdown system with categories (Search Ads, Social Media, etc.) and sub-options
- **UTM Medium Selection**: Predefined medium types (paid_search, paid_social, organic_social, etc.)
- **Dynamic Placeholders**: Option to use platform placeholders ({{campaign.name}}, {{ad.name}}) or static text
- **Platform Suggestions**: Auto-suggests utm_source and utm_medium based on selected platform (user can override)
- **URL History**: Stores last 100 generated URLs in JSON format
- **Validation**: Form validation ensures required fields are present
- **Test Mode**: Mock data system for development and testing
  - Realistic test data for all platforms
  - Preview full URLs with platform-specific parameters (gclid, fbclid, etc.)
  - Easy switching between test and production modes

## Installation

1. Ensure you have Python 3.8+ installed
2. Activate your virtual environment:
   ```bash
   # Windows
   venv\Scripts\activate
   
   # Mac/Linux
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. (Optional) Set up test mode:
   ```bash
   # Windows PowerShell
   $env:TEST_MODE="True"
   
   # Windows CMD
   set TEST_MODE=True
   
   # Mac/Linux
   export TEST_MODE=True
   ```
   
   Or create a `.env` file in the project root:
   ```
   TEST_MODE=True
   ```

## Usage

1. Start the Flask application:
   ```bash
   python app.py
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

3. Fill out the form:
   - Select a platform (e.g., Instagram)
   - Choose UTM Source Category (e.g., Social Media)
   - Select specific source from dropdown (e.g., instagram)
   - Select UTM Medium (e.g., paid_social)
   - Enter campaign name, ad name, ad set name (optional)
   - Check "Include Dynamic Placeholders" if you want {{placeholders}}
   - Click "Generate URL"

4. Copy the generated URL and use it in your ad campaigns

### Test Mode Features

When `TEST_MODE=True` is set:

- **Test Mode Banner**: Yellow banner at top indicates test mode is active
- **Example Values**: Placeholder examples show actual values (e.g., "Summer_Sale_2025" instead of "{{campaign.name}}")
- **Preview Full URL**: Button to preview what the URL would look like when it arrives at your site, including:
  - Platform-specific click IDs (gclid, fbclid, ttclid, msclkid)
  - Platform IDs (campaign_id, adset_id, ad_id, placement)
  - All UTM parameters

This helps you:
- Test Phase 2 parameter capture before going live
- Understand what parameters each platform adds
- Validate your tracking system with realistic data

## URL Structure

Generated URLs follow this pattern:
```
http://dnstrainer.com/landing?utm_source=instagram&utm_medium=paid_social&utm_campaign={{campaign.name}}&utm_content={{ad.name}}&utm_term={{adset.name}}
```

### Parameters Included:
- `utm_source` - Required (identifies platform)
- `utm_medium` - Required (traffic type)
- `utm_campaign` - Campaign name (dynamic placeholder or static)
- `utm_content` - Ad name (dynamic placeholder or static)
- `utm_term` - Ad set name (optional, dynamic placeholder or static)

### Parameters NOT Included (captured server-side):
- `gclid`, `fbclid`, `ttclid`, `msclkid` - Auto-tagged by platforms
- `campaign_id`, `adset_id`, `ad_id`, `placement` - Platform-specific IDs
- `session_id`, `referrer_url`, `timestamp` - System-generated

## Project Structure

```
DNStracking/
├── src/
│   ├── __init__.py
│   ├── url_generator.py      # Core URL building logic
│   ├── validators.py          # Form validation
│   ├── config.py              # Configuration and data loading
│   └── platform_suggestions.py # Platform → utm_source/medium mapping
├── templates/
│   └── index.html             # Web UI
├── data/
│   ├── utm_sources.json       # UTM source definitions
│   ├── utm_mediums.json       # UTM medium options
│   └── url_history.json       # Generated URL history
├── app.py                     # Flask application
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## Configuration

### UTM Sources
Edit `data/utm_sources.json` to modify source categories and options.

### UTM Mediums
Edit `data/utm_mediums.json` to modify available medium types.

### Platform Suggestions
Edit `src/platform_suggestions.py` to modify platform → utm_source/medium mappings.

### Base URL
Change `BASE_URL` in `src/config.py` to modify the landing page URL.

## API Endpoints

### POST `/api/generate`
Generate a tracking URL.

**Request Body:**
```json
{
  "platform": "Instagram",
  "utm_source": "instagram",
  "utm_medium": "paid_social",
  "campaign_name": "Summer Sale",
  "ad_name": "Video Ad 1",
  "adset_name": "Women 25-35",
  "use_dynamic_placeholders": true
}
```

**Response:**
```json
{
  "success": true,
  "url": "http://dnstrainer.com/landing?utm_source=instagram&...",
  "data": {
    "id": "uuid",
    "timestamp": "2025-01-XX...",
    "platform": "Instagram",
    ...
  }
}
```

### POST `/api/platform-suggestion`
Get suggested utm_source and utm_medium for a platform.

**Request Body:**
```json
{
  "platform": "Instagram"
}
```

**Response:**
```json
{
  "success": true,
  "utm_source": "instagram",
  "utm_medium": "paid_social"
}
```

### GET `/api/history`
Get URL generation history (last 100 entries).

### POST `/api/preview-full-url` (Test Mode Only)
Preview full URL with platform-specific parameters.

**Request Body:**
```json
{
  "platform": "Instagram",
  "utm_source": "instagram",
  "utm_medium": "paid_social",
  "campaign_name": "Summer Sale",
  "ad_name": "Video Ad 1",
  "adset_name": "Women 25-35",
  "use_dynamic_placeholders": true
}
```

**Response:**
```json
{
  "success": true,
  "utm_only_url": "http://dnstrainer.com/landing?utm_source=instagram&...",
  "full_url": "http://dnstrainer.com/landing?utm_source=instagram&...&fbclid=IwAR...&campaign_id=111222333",
  "platform": "Instagram"
}
```

## Test Mode vs Production Mode

### Test Mode (`TEST_MODE=True`)
- Uses mock data from `data/mock_data.json`
- Shows example placeholder values in UI
- Enables preview of full URLs with platform parameters
- Perfect for development and testing Phase 2

### Production Mode (`TEST_MODE=False` or unset)
- No mock data
- Shows placeholder syntax in UI ({{campaign.name}})
- Preview feature disabled
- Use for actual campaign URL generation

## Mock Data

Test scenarios are stored in `data/mock_data.json` and include:
- Google Ads (with gclid)
- Meta/Facebook (with fbclid, campaign_id, adset_id, ad_id, placement)
- Instagram (with fbclid, igshid, campaign_id, adset_id, ad_id, placement)
- TikTok (with ttclid)
- LinkedIn
- Microsoft Ads (with msclkid)
- Email campaigns

Each scenario includes realistic parameter formats matching real platform behavior.

## Next Steps (Future Phases)

- Phase 2: Parameter capture script for landing pages
- Phase 3: Tracking API and database storage
- Phase 4: ETL layer and analytics
- Phase 5: LLM analysis and optimization

## License

Proprietary - DNS Trainer

