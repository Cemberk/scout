# Connecting Scout to Google

Scout is a teammate. To give it access to Google things, you add it the same way you'd add a new hire: create a Google account for Scout, and then share the folders, calendars, and inboxes you want it to see.

This page walks you through creating Scout's Google identity once. After that, expanding Scout's access is just sharing a Drive folder or forwarding a calendar invite — no env changes, no redeploys.

## The model

| You do | Scout can now |
|---|---|
| Create a Google account for Scout (e.g. `scout@yourcompany.com` or a dedicated `gmail.com` address) | Have its own Gmail, Calendar, and Drive identity |
| Share a Drive folder with Scout's account | Search + read everything in that folder |
| Invite Scout's account to a calendar | See the events on that calendar |
| Forward email to Scout's inbox, or CC it | Read the thread |
| Stop sharing | Scout immediately loses access — no code change |

Scout authenticates as its own Google user. Nothing is scoped by env var or allowlist. The Google share graph is the access control.

## What Scout can and can't do

| Service | Scout can | Scout can't |
|---|---|---|
| **Gmail** | Search, read threads, create drafts, manage labels | Send email or replies directly |
| **Calendar** | View events, find free slots, list calendars | Create, update, or delete events |
| **Drive** (live-read `Source`) | Native Drive search across everything shared with Scout's account, read files, export Workspace docs to markdown/CSV | Any write — Drive is read-only |

Sending email is disabled by default. Scout creates drafts and tells you: *"Draft ready. Review and send when you're happy with it."* Set `SCOUT_ALLOW_SENDS=true` to let the Leader actually send on your behalf — off by default so nothing leaves your workspace without your say-so.

Calendar stays read-only regardless of `SCOUT_ALLOW_SENDS` in this build: the write scope isn't requested, and the write tools are stripped at construction.

## Step 1: Create a Google account for Scout

Skip this if Scout already has an account in your workspace.

- If you're on Google Workspace: create a user in the admin console (e.g. `scout@yourcompany.com`). Treat it like any other teammate.
- If you're not: make a regular `@gmail.com` account for Scout.

From here on, this doc assumes you're signed into **Scout's Google account**, not your personal one.

## Step 2: Create a Google Cloud project

One Cloud project powers all three services (Gmail, Calendar, Drive).

1. Go to [console.cloud.google.com](https://console.cloud.google.com) signed in as Scout.
2. Click the project dropdown (top-left) → **New Project**.
3. Name it `scout` and click **Create**.
4. Copy the **Project ID** → save as `GOOGLE_PROJECT_ID`.

## Step 3: Enable the APIs

Under **APIs & Services → Library**, enable:

- Gmail API
- Google Calendar API
- Google Drive API

## Step 4: Configure the OAuth consent screen

1. Go to **APIs & Services → OAuth consent screen**.
2. Click **Get started**.
3. **App Information**: app name `scout`, support email = Scout's Google address → **Next**.
4. **Audience**: select **External** → **Next**.
5. **Contact Information**: your email → **Next** → **Finish**.
6. Under **Audience**, add Scout's Google email as a **test user**.

In testing mode the OAuth token expires every 7 days. Publish the app through Google's verification flow if you want a long-lived token.

## Step 5: Create OAuth credentials

1. **APIs & Services → Credentials**.
2. **Create Credentials → OAuth client ID**.
3. Application type: **Desktop app**. Name: `scout-desktop` → **Create**.
4. Copy **Client ID** → `GOOGLE_CLIENT_ID`.
5. Copy **Client secret** → `GOOGLE_CLIENT_SECRET`.

## Step 6: Add credentials to `.env`

```env
GOOGLE_CLIENT_ID="your-google-client-id"
GOOGLE_CLIENT_SECRET="your-google-client-secret"
GOOGLE_PROJECT_ID="your-google-project-id"
```

All three are required together. If any are missing, Scout disables Gmail, Calendar, and Drive with a clear message directing you back here.

## Step 7: Generate `token.json`

Run the OAuth script on the host (not inside Docker). The script needs `google-auth-oauthlib`, which ships with the project's dev install — activate the venv first if you haven't (`./scripts/venv_setup.sh && source .venv/bin/activate`).

```sh
set -a; source .env; set +a
python scripts/google_auth.py
```

This opens a browser. **Sign in as Scout's Google account**, not your personal one. Grant the consent screen's requested scopes. The script writes `token.json` to the repo root.

## Step 8: Share things with Scout

Now you decide what Scout sees:

- **Drive**: share a Drive folder with Scout's Google address. That entire folder (recursively) becomes searchable and readable.
- **Calendar**: on any calendar you want Scout to monitor, use *Settings → Share with specific people* and add Scout's address. For the default primary calendar, Scout already sees it.
- **Gmail**: there's nothing to share — Scout reads its own inbox. Forward or CC Scout on threads you want it to know about.

Un-share at any time to revoke access. Scout's view updates on the next query — no redeploy needed.

## Step 9: Restart Scout

```sh
docker compose up -d --build
```

Verify: `GET http://localhost:8000/contexts` lists the registered contexts and their health. `gmail` / `drive` should report `connected`. Ask Scout a question — Explorer reads email, lists calendar events, and searches Drive via `query_gmail` / `query_drive`.

## Troubleshooting

### Token expired (7-day limit)

Testing-mode OAuth tokens expire every 7 days. Regenerate:

```sh
set -a; source .env; set +a
python scripts/google_auth.py
docker compose restart scout-api
```

Publishing the app through Google's verification flow removes the limit.

### "Access blocked" error

Scout's email must be a test user on the OAuth consent screen. Go to **APIs & Services → OAuth consent screen → Audience** and add it.

### Drive folder isn't showing up

Drive scope comes from what's shared with Scout's Google account, not from env vars. If a folder isn't appearing:

1. Open the folder in Drive as Scout's account — can Scout see it?
2. If not, re-share the folder. Wait 30 seconds; Google's index is eventually consistent.
3. `GET /contexts` should show `drive` as `connected`. If it's `disconnected` with a "missing: ['GOOGLE_*']" detail, the Google env vars aren't set.

### "Missing credentials"

All three of `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_PROJECT_ID` are required together. If any is missing, Gmail, Calendar, and Drive stay off.

### OAuth scopes

`scripts/google_auth.py` requests:

- `gmail.readonly` — read email
- `gmail.modify` — manage labels, mark read/unread
- `gmail.compose` — create drafts
- `calendar` — read calendar (Scout doesn't use write ops in this build)
- `drive.readonly` — read anything shared with Scout's account

## How it works

1. `scripts/google_auth.py` runs an OAuth flow. You sign in as Scout; Google hands back a refresh token.
2. The script writes `token.json` to the repo root.
3. In Docker, `token.json` is available to the container via the `.:/app` bind mount in `compose.yaml`. It is not baked into the image (`.dockerignore` excludes it).
4. At startup:
   - If the three Google env vars are set, `scout/team.py` loads `GmailTools` (send functions excluded unless `SCOUT_ALLOW_SENDS=true`) and `GoogleCalendarTools` (read-only unless `SCOUT_ALLOW_SENDS=true`) on the **Leader**.
   - If you register `gmail` and/or `drive` in `SCOUT_CONTEXTS`, `GmailContextProvider` and `DriveContextProvider` come up as live-read contexts for **Explorer** and share the same `token.json`.
5. Health probes (`health("gmail")` / `health("drive")`) short-circuit to `DISCONNECTED` with a fixit hint when `token.json` is missing — so a fresh container won't hang on a browser-opening OAuth flow.

`token.json` contains OAuth tokens — it's in `.gitignore` and `.dockerignore`. Don't commit it.
