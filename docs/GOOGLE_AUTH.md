# Google Authentication (Gmail + Calendar + Drive)

Google OAuth gives Scout access to Gmail, Google Calendar, and Google Drive. You need three values: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_PROJECT_ID`.

This setup is a one-time process. After completing it, Scout can search email, read threads, create drafts, view your calendar, and list/read files from shared Drive folders.

## What Scout Can Do

| Service | Enabled | Disabled |
|---------|---------|----------|
| **Gmail** | Search, read threads, create/list drafts, manage labels | Send email, send replies |
| **Calendar** | View events, fetch by date, find available slots, list calendars | Create events, update events, delete events |
| **Drive** (as a live-read `Source`) | Native Drive search (`fullText contains`), read files, export Workspace docs to markdown/CSV | Any write — Drive is read-only |

Sending email is disabled at the code level. Scout always creates drafts: "Draft created in Gmail. Review and send when ready."

Calendar is read-only in this build — `create_event` / `update_event` / `delete_event` are stripped at Toolkit construction time via `exclude_tools`, and the OAuth scope stays read-only.

## Step 1: Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click the project dropdown (top-left) → **New Project**
3. Name it (e.g., `agents`) and click **Create**
4. Copy the **Project ID** from the project dashboard → save as `GOOGLE_PROJECT_ID`

## Step 2: Enable the APIs

1. Go to **APIs & Services → Library**
2. Search for and enable **Gmail API**
3. Search for and enable **Google Calendar API**
4. Search for and enable **Google Drive API**

## Step 3: Configure the OAuth Consent Screen

1. Go to **APIs & Services → OAuth consent screen**
2. Click **Get started**
3. **App Information**: Enter an app name (e.g., `scout`) and your support email → **Next**
4. **Audience**: Select **External** → **Next**
5. **Contact Information**: Enter your email → **Next**
6. **Finish**: Click **Create**
7. Go to **Audience** in the sidebar and add your Google email as a test user

## Step 4: Create OAuth Credentials

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Application type: **Desktop app**
4. Name it (e.g., `scout-desktop`) → **Create**
5. Copy **Client ID** → `GOOGLE_CLIENT_ID`
6. Copy **Client secret** → `GOOGLE_CLIENT_SECRET`

## Step 5: Add to `.env`

```env
GOOGLE_CLIENT_ID="your-google-client-id"
GOOGLE_CLIENT_SECRET="your-google-client-secret"
GOOGLE_PROJECT_ID="your-google-project-id"
```

If you want Scout to live-read specific Drive folders, also add:

```env
GOOGLE_DRIVE_FOLDER_IDS="1abc...,1def..."
```

Comma-separated folder IDs. Empty = Gmail + Calendar only, no Drive source.

## Step 6: Generate `token.json`

Run the OAuth script on your local machine (not inside Docker):

```sh
set -a; source .env; set +a
python scripts/google_auth.py
```

This opens a browser for Google consent and saves `token.json` to the project root. The script uses `prompt='consent'` so a refresh token is always returned, even on re-authorization.

## Step 7: Restart Scout

```sh
docker compose up -d --build
```

Gmail, Calendar, and (if `GOOGLE_DRIVE_FOLDER_IDS` is set) Drive are now configured. `GET /manifest` should show `drive` as `connected`.

## Troubleshooting

### Token Expired (7-day limit)

Google defaults to "Testing" mode, which expires tokens every 7 days. When this happens:

```sh
set -a; source .env; set +a
python scripts/google_auth.py
docker compose up -d --build
```

Publishing the app through Google's verification process removes the 7-day limit.

### "Access blocked" Error

Your Google email must be added as a test user in the OAuth consent screen:
1. Go to **APIs & Services → OAuth consent screen → Audience**
2. Add your email under **Test users**

### Missing Credentials

All three values are required together. If any are missing, Scout disables Gmail and Calendar with fallback text:

> Gmail isn't set up yet. Follow the setup guide in `docs/GOOGLE_AUTH.md` to connect your Google account.

### OAuth Scopes

`scripts/google_auth.py` requests:

- `gmail.readonly` — read email
- `gmail.modify` — manage labels, mark read/unread
- `gmail.compose` — create drafts
- `calendar` — calendar access (Scout only uses read operations in this build)
- `drive.readonly` (optional, added when `GOOGLE_DRIVE_FOLDER_IDS` is set)

## How It Works

1. `scripts/google_auth.py` runs an OAuth flow that opens a browser for consent.
2. On success, it saves `token.json` to the project root with access and refresh tokens.
3. At startup, `scout/tools/build.py` checks `GOOGLE_INTEGRATION_ENABLED` (all three env vars set).
4. If yes: `GmailTools` is loaded with `exclude_tools=['send_email','send_email_reply']`, and `GoogleCalendarTools` with `allow_update=False` plus `exclude_tools=['create_event','update_event','delete_event']`.
5. If no: the disabled-instruction blocks are appended to the Navigator's prompt, and no Google tool calls are attempted.
6. `GoogleDriveSource` is registered separately — it depends on the Google env **and** `GOOGLE_DRIVE_FOLDER_IDS`. It reuses the same `token.json`.

`token.json` is picked up from the project root inside the Docker container via the `.:/app` bind mount in `compose.yaml`. It contains OAuth tokens — do not commit it to version control (it's in `.gitignore`).
