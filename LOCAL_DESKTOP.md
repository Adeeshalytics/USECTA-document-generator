# USECTA desktop edition — Windows 10/11, Intel/AMD 64-bit

Use the app locally from a desktop shortcut. No IDE, hosting, Supabase account or monthly payment is needed. It opens in your normal browser and stores the company workspace in `data/` beside the app. Cloud secrets are ignored by the desktop launcher. PDF generation uses local LibreOffice and batches multiple documents to reduce repeated startup time.

## On your computer: set up once

1. Download the latest GitHub ZIP and extract it into a permanent folder, for example `C:\USECTA`. Do not run from inside the ZIP.
2. Double-click **setup-desktop.bat**. Internet is needed for this first setup. It downloads an official portable Python runtime, installs the app dependencies, and bundles LibreOffice. If LibreOffice is already installed it copies that installation; otherwise it extracts an official signed installer. Windows may request permission during LibreOffice extraction. Publisher/signature checks stay enabled.
3. Wait for **Setup complete**. Setup checks DOCX and PDF generation and creates **USECTA Documents** and **Stop USECTA Documents** shortcuts on your desktop.
4. Double-click **USECTA Documents** whenever you want to work. No console window stays open. Opening it again reuses the running app.

This first setup downloads hundreds of megabytes and is slower than everyday use. Keep the whole folder together; the Python and LibreOffice folders are part of the app. Normal document work runs offline afterward.

The app does not need a login locally. It binds to `127.0.0.1` so the workspace is available on this computer. It saves suppliers, tenders, template versions and run history in `data/`. Downloaded DOCX/PDF files go wherever your browser saves downloads.

Closing the browser tab leaves the app running for a quick reopen. To stop it, use **Stop USECTA Documents**. If the computer restarts, simply open **USECTA Documents** again. Startup failures are reported in a message box and `data/desktop.log`.

## Give a copy to the other director

1. Double-click **Make USB copy.bat** on your computer after setup succeeds.
2. Choose whether to include your saved **local** supplier details, catalogues, templates and history. Answer `y` to include them, or press Enter for a fresh workspace with the supplied six templates, quotation starter and SPMC/03/2026 catalogue.
3. The script opens `dist/`. Copy the newly created **USECTA-Desktop-...** folder to the pendrive. It includes Python, LibreOffice and the app. It excludes Supabase secrets, Git files, developer environments, setup downloads and logs.
4. On the director's Windows PC, copy that whole folder to a permanent location such as `C:\USECTA`.
5. Double-click **Create desktop shortcuts.bat** once, then open **USECTA Documents** from the desktop.

The director does **not** need to install Python or LibreOffice or repeat the internet setup. If a Windows component/DLL is missing, run `runtime/python/python.exe scripts/check-desktop.py` from the copied folder to identify the failure before use; the setup checks on your computer cannot prove compatibility with every other PC. This package is for Windows Intel/AMD 64-bit, not Mac or ARM Windows.

Copying to the computer is recommended for speed and dependable saves. You can also run **Open USECTA.bat** directly from a writable pendrive. Close USECTA before unplugging it; disconnecting during a database write can damage saved data. If you move the folder later, recreate the desktop shortcuts.

Each computer has its **own** records after copying. Changes do not automatically sync between directors. To share a workspace snapshot, stop the app on both computers, back up the destination `data/` folder, and copy the source's complete `data/` folder. This replaces the destination workspace; it does not merge two sets of changes.

## Existing records and templates

Extracting a fresh GitHub ZIP does not bring over your local records automatically. Stop the old app and copy its `data/` folder into the new folder before running the desktop edition. Keep a backup. New template versions are imported without replacing old versions or edited tender catalogues.

Supabase records are also not downloaded automatically. For cloud-only data, upload custom templates and import your catalogues into this local copy, and re-enter supplier details. Saved cloud history remains in Supabase.

The bid acceptance validity date is still required for a Bid Form. Enter it in **Tenders & items**; the app does not infer it from the closing date.

## PDFs and formatting

LibreOffice is bundled locally, so PDF generation does not contact a hosted server. DOCX formatting, bold/uppercase placeholders and template versions follow the same rules as the existing app. The desktop kit detects bundled LibreOffice or a normal Windows installation automatically; changing PATH is unnecessary.

Fonts come from the Windows computer. For consistent output, ensure the fonts used by your templates are installed on both PCs, and check a sample agreement and long item description. LibreOffice and Microsoft Word can differ in pagination. Existing Word layouts are not rebuilt or shrunk.

## Backup and updates

Stop USECTA and copy the full `data/` folder to your backup drive. Keep generated documents you need to retain. If updating source files later, keep `data/` and `runtime/`, then rerun `setup-desktop.bat` to check/update dependencies. Keep a backup before replacing files.

If you already use the original `.venv` installation, **run-windows.bat** now forces local mode as well. The new desktop setup is what provides the self-contained folder for transfer to another PC.

## Ready-made Windows download from GitHub

The **Windows desktop package** GitHub Actions workflow prepares and checks the portable folder on a Windows runner. Once its run succeeds, sign into GitHub, open **Actions → Windows desktop package → latest successful run**, and download **USECTA-Desktop-Windows-x64** under Artifacts. Extract that ZIP into a permanent folder and run **Create desktop shortcuts.bat**; the runtime is already included. Artifacts expire after 30 days, so keep your downloaded copy. You can rebuild it through **Run workflow**. The normal repository source ZIP still needs the first-time `setup-desktop.bat` preparation.
