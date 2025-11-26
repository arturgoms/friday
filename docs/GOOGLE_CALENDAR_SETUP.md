# Google Work Calendar Integration - Setup Guide

## 📅 Overview

Your Friday AI now supports **multiple calendars**:
- **Nextcloud Calendar** (Personal)
- **Google Calendar** (Work) ← NEW!

Events from both calendars will be merged and displayed together in your morning and evening reports.

---

## 🚀 Setup Steps

### STEP 1: Create Google Cloud Project & Enable API

1. Go to https://console.cloud.google.com/
2. Create a new project or select an existing one
3. Enable the Google Calendar API:
   - Click "APIs & Services" → "Library"
   - Search for "Google Calendar API"
   - Click "ENABLE"

### STEP 2: Create OAuth 2.0 Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "CREATE CREDENTIALS" → "OAuth client ID"
3. Configure OAuth consent screen (if not done):
   - User Type: Internal (if using workspace) or External
   - App name: "Friday AI"
   - Add your email as test user (if External)
4. Create OAuth client ID:
   - Application type: **Desktop app**
   - Name: "Friday AI Calendar"
   - Click "CREATE"
5. **Download the credentials JSON file**
6. Save it as: `/home/artur/friday/data/google_credentials.json`

### STEP 3: Add Configuration to .env

Add this line to `/home/artur/friday/.env`:

```bash
# Google Calendar Configuration
GOOGLE_CALENDAR_ID=your.work.email@company.com
```

**Notes:**
- Replace `your.work.email@company.com` with your actual work email
- Or use `"primary"` for your main Google Calendar
- To find your calendar ID:
  1. Go to Google Calendar settings
  2. Click on your calendar
  3. Scroll to "Integrate calendar"
  4. Copy the "Calendar ID"

### STEP 4: First-Time Authentication

The first time Friday connects to Google Calendar:

1. A browser window will automatically open
2. Sign in to your Google work account
3. Review the permissions Friday is requesting:
   - ✅ "See events on all your calendars" (read-only)
4. Click "Allow"
5. The authentication token will be saved for future use at:
   `/home/artur/friday/data/google_token.pickle`

**Note:** You only need to do this once! The token will automatically refresh.

---

## 📋 File Checklist

Make sure these files exist:

- ✅ `/home/artur/friday/data/google_credentials.json` (OAuth client credentials)
- ✅ `/home/artur/friday/.env` (contains GOOGLE_CALENDAR_ID)
- ⏳ `/home/artur/friday/data/google_token.pickle` (created after first auth)

---

## 🧪 Testing

Test the Google Calendar integration:

```bash
cd /home/artur/friday
python3 << 'ENDPYTHON'
import sys
sys.path.insert(0, '/home/artur/friday/src')

from app.services.unified_calendar_service import unified_calendar_service

# Get today's events from all calendars
events = unified_calendar_service.get_today_events()

print("=" * 60)
print("TODAY'S EVENTS FROM ALL CALENDARS")
print("=" * 60)

if events:
    for event in events:
        print(f"• {event.start.strftime('%I:%M %p')} - {event.summary}")
        if event.location:
            print(f"  📍 {event.location}")
else:
    print("No events found today")

print("=" * 60)
ENDPYTHON
```

---

## 📱 What You'll See

After setup, your morning (9 AM) and evening (11 PM) reports will include events from **both calendars**:

### Morning Report Example:
```
📅 **Today's Schedule:**
• 08:00 AM - Morning Routine  [Nextcloud]
• 09:30 AM - Team Standup [Google Work]
• 02:00 PM - Client Meeting [Google Work]
• 06:30 PM - Take out trash [Nextcloud]
```

---

## 🔧 Troubleshooting

### "Credentials file not found"
- Make sure `google_credentials.json` is in `/home/artur/friday/data/`
- Check file permissions: `chmod 600 /home/artur/friday/data/google_credentials.json`

### "Failed to refresh token"
- Delete the old token: `rm /home/artur/friday/data/google_token.pickle`
- Restart Friday to re-authenticate

### "Calendar not connected"
- Check that `GOOGLE_CALENDAR_ID` is set in `.env`
- Verify you granted permissions during OAuth flow
- Check Friday logs: `journalctl -u friday -f`

### Events not showing
- Verify the calendar ID is correct
- Make sure events exist in the time range
- Check if calendar is shared/accessible to your account

---

## 🔒 Security Notes

- OAuth credentials are stored securely in `/home/artur/friday/data/`
- Friday only requests **read-only** access to your calendars
- Tokens are automatically refreshed - no password storage
- Set restrictive permissions: `chmod 600 /home/artur/friday/data/google_*`

---

## ✅ Next Steps

Once setup is complete:

1. Restart Friday: `sudo systemctl restart friday`
2. Check logs for successful connection:
   ```
   ✅ Connected to Google Calendar (ID: your.email@company.com)
   ```
3. Wait for your next morning (9 AM) or evening (11 PM) report
4. Verify events from both calendars appear

---

## 🎉 You're Done!

Your Friday AI now has complete visibility across both personal and work calendars! 

**Questions?** Check the logs or test the integration using the test script above.
