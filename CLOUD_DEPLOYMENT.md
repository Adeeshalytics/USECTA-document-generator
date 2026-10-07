# Streamlit + Supabase deployment

The app supports local SQLite or a shared company workspace in Supabase. All approved users can read and edit the same company records. DOCX rendering still preserves the template formatting; LibreOffice generates PDFs on the cloud server.

## 1. Set up the database and private bucket

In your Supabase project, open **SQL Editor**, paste the contents of `supabase/setup.sql`, and run it. This creates the app's database table, denies browser/direct user access, and creates (or keeps private) the `document-templates` bucket. Do not add public bucket policies or turn off row level security.

## 2. Create company login accounts

Under **Authentication → Providers**, enable Email/password. Disable public sign-ups in Authentication settings. Under **Authentication → Users → Add user**, create your own user with an email and strong password (use the auto-confirm option for an administrator-created account). Create additional accounts only for company users who need access. Also add their email addresses to `ALLOWED_EMAILS` below.

## 3. Deploy from GitHub

In Streamlit Community Cloud, create an app from:

- Repository: `Adeeshalytics/USECTA-document-generator`
- Branch: `main`
- Main file: `app.py`
- Python: 3.12

Before starting the deployment, open **Advanced settings → Secrets** and enter:

```toml
STORAGE_BACKEND = "supabase"
SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
SUPABASE_SECRET_KEY = "YOUR-SERVER-SECRET-KEY"
SUPABASE_PUBLISHABLE_KEY = "YOUR-PUBLISHABLE-KEY"
ALLOWED_EMAILS = ["your-company-email@example.com"]
```

Get the URL and keys from your Supabase project's connection/API-key settings. The **secret key** (or legacy `service_role` key) is privileged and stays on the Streamlit server. The **publishable key** (or legacy `anon` key) is used for login. Never put real keys in GitHub or chat. No database password is needed by the app.

These five settings enable cloud mode. Without `STORAGE_BACKEND = "supabase"`, the app uses local SQLite; do not deploy for company use without configuring Secrets first.

Deploy. Streamlit installs Python dependencies from `requirements.txt` and LibreOffice/fonts from `packages.txt`. No LibreOffice installation is needed on your own computer for the hosted app.

## 4. First login and checks

Sign in with the account created in Supabase. On first login the app imports the six supplied templates, quotation starter, and SPMC/03/2026 catalogue into Supabase. Existing saved templates and edited catalogues are retained on subsequent starts.

Enter the bid acceptance validity date in **Tenders & items** before generating a Bid Form.

- Save a supplier and confirm it survives a Streamlit reboot.
- Upload a template and confirm it is available after reboot.
- Generate DOCX and PDF for a long item name and agency agreement.
- Compare fonts, uppercase/bold text, logo, watermark and page breaks with Word. LibreOffice font substitutions can affect wrapping; Carlito and Caladea provide compatible alternatives to Calibri and Cambria. No forced font shrinking or layout changes are applied.
- Sign out and confirm records/downloads are hidden until signing in again.

Login expires after at most one hour and requires signing in again. No user tokens or passwords are saved in the database. All approved users share the same company workspace; there are no per-user or read-only roles.

Generated files are offered as downloads. Saved run details and template versions are permanent in Supabase, allowing regeneration. Generated PDFs themselves are not uploaded to storage.

## Existing local data and backups

Cloud mode imports the shipped assets, **not your existing local `data/` folder**. Keep a copy of that folder. Upload your custom templates, re-enter supplier details, and import edited catalogues through the app. Old local history remains available when running locally.

Back up important records/templates separately. Free hosting and Supabase plans have usage limits and may pause inactive services; they are not a guarantee of uninterrupted availability. Restore the Supabase project if it is paused before restarting the app.

## Local use

Without a Secrets file the app continues to use local SQLite. To test cloud mode locally, place the same settings in `.streamlit/secrets.toml` (ignored by Git). Local PDF generation still requires LibreOffice installed on the computer.
