# Google Calendar Integration Setup Guide

This guide explains how to set up Google Calendar integration for the CLAT Preparation Hub.

## Overview

The calendar feature requires:
1. A Google Cloud Platform (GCP) project
2. OAuth 2.0 credentials for web application
3. Enabled APIs: Calendar API, Gmail API

## Step 1: Create or Select a GCP Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your **Project ID**

## Step 2: Enable Required APIs

In Google Cloud Console:

1. Go to **APIs & Services** → **Library**
2. Search for and enable:
   - **Google Calendar API**
   - **Gmail API**
   - **People API** (for user profile info)

## Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Select **Internal** (if using Google Workspace) or **External**
3. Fill in the required fields:
   - **App name**: `CLAT Preparation Hub`
   - **User support email**: Your email
   - **Developer contact email**: Your email
4. Add scopes:
   - `https://www.googleapis.com/auth/calendar`
   - `https://www.googleapis.com/auth/gmail.send`
   - `https://www.googleapis.com/auth/userinfo.email`
   - `https://www.googleapis.com/auth/userinfo.profile`
5. Add test users (for External apps):
   - `k12arvind@gmail.com`
   - `arvind@orchids.edu.in`
   - `arvind@k12technoservices.com`

## Step 4: Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **+ CREATE CREDENTIALS** → **OAuth client ID**
3. Select **Web application**
4. Configure:
   - **Name**: `CLAT Calendar Integration`
   - **Authorized JavaScript origins**:
     ```
     http://localhost:8001
     https://speedmathsgames.com
     ```
   - **Authorized redirect URIs**:
     ```
     http://localhost:8001/api/calendar/callback
     https://speedmathsgames.com/api/calendar/callback
     ```
5. Click **CREATE**
6. Download the JSON file

## Step 5: Install Credentials

1. Rename the downloaded file to `google_oauth_credentials.json`
2. Place it in the project config folder:
   ```
   ~/clat_preparation/config/google_oauth_credentials.json
   ```
3. On Mac Mini (production):
   ```
   /Users/arvindkumar/clat_preparation/config/google_oauth_credentials.json
   ```

### Create the config directory if it doesn't exist:
```bash
mkdir -p ~/clat_preparation/config
```

## Step 6: Verify Installation

1. Restart the server:
   ```bash
   ssh mac-mini "cd ~/clat_preparation && git pull && bash scripts/deploy_resilient_services.sh"
   ```

2. Check server logs for confirmation:
   ```bash
   ssh mac-mini "tail -20 ~/clat_preparation/logs/server.log | grep -i calendar"
   ```

You should see:
```
✅ Calendar module initialized
✅ Google OAuth credentials found at /Users/arvindkumar/clat_preparation/config/google_oauth_credentials.json
```

## Step 7: Connect Google Accounts

1. Visit https://speedmathsgames.com/calendar.html
2. Click **Connect Google Account**
3. Sign in with each account:
   - `k12arvind@gmail.com` (primary - bills will sync here)
   - `arvind@orchids.edu.in`
   - `arvind@k12technoservices.com`
4. Authorize the requested permissions

## Features After Setup

### Calendar Features
- **View events** from all 3 accounts in one unified calendar
- **Day/Week/Month views** with color-coded accounts
- **Create/Edit events** directly from the web interface
- **Bill due dates** displayed on the calendar

### Bill Integration
- Bills automatically appear as calendar events
- Synced to `k12arvind@gmail.com` calendar
- Reminders at: 7 days, 3 days, 2 days, 1 day before, and on due date

### Daily Summary Email (8 AM)
- Sent to: `arvind@orchids.edu.in`
- Contains:
  - Today's events from all 3 calendars
  - Bill reminders for bills due in 7/3/2/1/0 days

## Troubleshooting

### "OAuth credentials file not found"
Ensure the credentials file is at:
```
~/clat_preparation/config/google_oauth_credentials.json
```

### "Access blocked: This app's request is invalid"
Check that redirect URIs in GCP Console exactly match:
- `http://localhost:8001/api/calendar/callback`
- `https://speedmathsgames.com/api/calendar/callback`

### "This app isn't verified"
For External OAuth consent screen, you'll see this warning. Click "Advanced" → "Go to CLAT Preparation Hub (unsafe)" to proceed during testing.

### Token Refresh Issues
If tokens expire:
1. Go to calendar.html
2. Click the account in sidebar
3. Re-authenticate

## Security Notes

1. **Never commit** `google_oauth_credentials.json` to git
2. The file is already in `.gitignore`
3. OAuth tokens are stored in `calendar_tracker.db` (also gitignored)
4. Access is restricted to users with `can_access_private_modules` permission

## File Locations

| File | Location | Purpose |
|------|----------|---------|
| OAuth Credentials | `config/google_oauth_credentials.json` | GCP OAuth client secrets |
| Calendar Database | `calendar_tracker.db` | OAuth tokens, cached events |
| Daily Summary Log | `logs/daily_summary.log` | Email job logs |

## Contact

For issues with the calendar integration, check:
1. Server logs: `~/clat_preparation/logs/server_error.log`
2. Calendar database: `sqlite3 calendar_tracker.db ".tables"`
3. Google Cloud Console for API errors

