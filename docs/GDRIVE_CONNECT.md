# Connecting Scout to Google Drive

Scout reads Google Drive through a **service account** — a headless Google identity Scout acts as. You share the folders you want Scout to see with the service account's email, and Scout can then search and read them. No per-user OAuth, no browser consent flow.

Two flavors:

- **Per-folder sharing** — simplest. Share specific Drives, folders, or files with the service account email. Scout sees only what's shared.
- **Domain-wide delegation** — for Google Workspace admins. The service account impersonates a real user (set `GOOGLE_DELEGATED_USER`), so it sees everything that user sees.

Start with per-folder sharing unless you need delegation.

## Step 1: Create a Google Cloud project

Skip this if you already have a GCP project you want to use.

1. Go to [console.cloud.google.com](https://console.cloud.google.com).
2. Click the project selector in the top bar → **New Project**.
3. Name it (e.g. `scout-drive`) and click **Create**.
4. Once created, make sure the new project is selected in the top bar.

## Step 2: Enable the Google Drive API

1. In the sidebar, go to **APIs & Services → Library**.
2. Search for **Google Drive API**.
3. Click it, then click **Enable**.

## Step 3: Create a service account

1. In the sidebar, go to **IAM & Admin → Service Accounts**.
2. Click **Create Service Account**.
3. Service account name: e.g. `scout-reader`. Click **Create and Continue**.
4. Skip the "Grant this service account access to project" step (click **Continue**).
5. Skip "Grant users access" (click **Done**).
6. You're back on the service accounts list. Copy the service account's **email address** (it looks like `scout-reader@your-project.iam.gserviceaccount.com`). You'll share folders with this.

## Step 4: Download the JSON key

1. Click the service account you just created.
2. Go to the **Keys** tab.
3. Click **Add Key → Create new key**.
4. Choose **JSON** and click **Create**. A JSON file downloads — treat it like a password.
5. Move it somewhere Scout can read:

```bash
mkdir -p ~/.scout
mv ~/Downloads/your-project-*.json ~/.scout/service-account.json
chmod 600 ~/.scout/service-account.json
```

## Step 5: Share folders with the service account

For each Google Drive folder you want Scout to see:

1. Right-click the folder in Drive → **Share**.
2. Paste the service account email from Step 3.
3. Role: **Viewer** (read-only is all Scout needs).
4. Click **Send** (or **Share** for workspace accounts). Uncheck "Notify people" — the service account doesn't have an inbox.

Repeat for every folder Scout should access. Shared Drives work the same way (share the Shared Drive root).

## Step 6: Set environment variables

Add to your `.env`:

```bash
GOOGLE_SERVICE_ACCOUNT_FILE=/absolute/path/to/service-account.json

# Optional — domain-wide delegation (skip for per-folder sharing)
# GOOGLE_DELEGATED_USER=user@yourdomain.com
```

Restart Scout:

```bash
docker compose up -d
```

## Verify

```bash
curl -sS http://localhost:8000/contexts | jq '.[] | select(.id == "gdrive")'
```

Expected:

```json
{ "id": "gdrive", "name": "Google Drive", "ok": true, "detail": "gdrive" }
```

Then ask Scout in chat:

> *"Search Drive for files with 'roadmap' in the name."*

Scout's **Explorer** will route to the GDrive context and return matches with links.

## Domain-wide delegation (optional)

If you want Scout to see everything a specific user sees (not just folders explicitly shared with the service account), your Workspace admin needs to grant the service account domain-wide authority:

1. In GCP Console → Service account → **Details** → **Show Advanced Settings** → copy the **Client ID** (a long number).
2. In Google Workspace Admin ([admin.google.com](https://admin.google.com)) → **Security → Access and data control → API controls → Domain-wide delegation**.
3. Click **Add new**. Paste the Client ID. OAuth scopes: `https://www.googleapis.com/auth/drive.readonly`.
4. Set `GOOGLE_DELEGATED_USER=user@yourdomain.com` in Scout's `.env`.

Scout will then impersonate that user when calling Drive. Scope stays read-only; Scout cannot write to Drive either way.

## Security notes

- The JSON key is a credential. Don't commit it. Don't paste it into chat. Rotate it in GCP Console if exposed.
- Role on shared folders is **Viewer** — Scout cannot modify or delete your files. The Drive toolkit also runs with `upload_file=False, download_file=False` in Scout's code (see [`scout/context/gdrive/provider.py`](../scout/context/gdrive/provider.py)).
- The service account has no access to Drive content it hasn't been explicitly shared on, unless you use domain-wide delegation.

## Troubleshooting

- **`/contexts` shows `ok: false, detail: "service account file not found"`** — the path in `GOOGLE_SERVICE_ACCOUNT_FILE` doesn't exist inside the container. If you're using Docker Compose, make sure the path is reachable from the container (mount your key into `/app/...` or similar).
- **Queries return "permission denied" / 403** — the file or folder isn't shared with the service account email. Re-check Step 5.
- **Queries return no results** — check you shared folders (not just individual files) if you're searching broadly. Also verify the JSON is valid: `python -m json.tool ~/.scout/service-account.json`.
- **Domain-wide delegation is set but doesn't work** — the OAuth scope in Workspace Admin must exactly match `https://www.googleapis.com/auth/drive.readonly`. Typos here silently fail.
