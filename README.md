# USECTA Document Generator

Create recurring tender letters, bid forms, agreements, and independent quotations locally. No LLM, API key, or paid service is required. USECTA's company name, address, branding, and fixed wording stay in the Word templates.

## Run on Windows

Requires Python 3.12 or newer. Extract the project into a normal folder, then double-click **setup-windows.bat** once and **run-windows.bat** to start the application.

Alternatively, open PowerShell in the project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the browser address printed in the terminal. Keep the terminal open; press Ctrl+C to stop the app. On later runs, only the last command is needed.

If updating an existing installation, stop the app, back up **data/**, and copy the new source files into the same project folder. Keep your existing **data/** and **.venv/** folders. Rerun the dependency-install command above. The database migration preserves old templates, profiles, and saved projects. Earlier projects remain downloadable as JSON; new runs can also be regenerated directly.

The GitHub download includes **company_templates/** with the six checked USECTA templates. They import automatically into the local template library the first time you run the updated app. You can upload later template versions in the Templates tab.

## Run on macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

For PDF downloads install free **LibreOffice** and make `libreoffice` or `soffice` available on PATH. On Windows this is usually `C:\Program Files\LibreOffice\program`; on macOS it is `/Applications/LibreOffice.app/Contents/MacOS`. Restart the app after installation. DOCX downloads work without LibreOffice.

## Tender workflow

**SPMC/03/2026** is preloaded on a fresh installation with the user's supplied 50-item catalogue, quantities in kg, document fees in LKR, and closing date **3 November 2026 at 10:00 a.m.** Its bid acceptance validity date is intentionally blank because it has not been supplied. Existing saved tender catalogues are never overwritten by this initial import.

1. In **Suppliers**, save a supplier's name, country, registration number, and address. Name alone is sufficient for cover letters; the agreement requires the other party details too.
2. In **Tender documents**, select the tender reference and document templates.
3. Search/select item numbers. Descriptions, quantities, and fees load from that tender's catalogue. An item number from another tender is never substituted.
4. Select the supplier for those items. For supplier documents, select only the items from that supplier. Repeat for other suppliers.
5. Set the letter/bid-form date and agreement effective date.
6. Generate, review, and download DOCX files, PDFs, or the complete ZIP. Generation also saves the input details as a run for future regeneration.

Output scopes:

| Document | Generated output |
| --- | --- |
| Bid document collection letter | One letter with selected items and document fees |
| Authorized personnel letter | One letter listing selected items |
| Agency agreement | One agreement for the selected supplier and selected items |
| Cover letter | One letter per selected item |
| Bid form | One form per selected item |
| Envelope covers | One document for the tender; item selection is optional |

The collection template is named **Bid Document (wider item column)**. Its columns use 12% for Item No, 68% for the item description, and 20% for the document fee. When updating an existing installation, the new template imports as a separate version; select that version instead of the older **Bid Document** template. You can also download the updated `company_templates/Bid Document.docx` from GitHub and upload it in Templates using the new name.

For a bid form, first enter the **bid acceptance validity date** in **Tenders & items**. This is the date until which the offer remains open for acceptance; it is different from the tender closing date. The app does not guess it or add an assumed number of days.

### Add another tender

In **Tenders & items**, save its reference, title, closing date/time, and optional bid validity date. Then choose that tender's catalogue and add rows manually or import CSV / XLSX. Required column headers:

```csv
item_number,description,document_fee,quantity_kg
```

`quantity_kg` is optional. `document_fee` is the non-refundable document fee in LKR, not the product price or bid security. Use `0` for a free document. The first worksheet is used for XLSX files. A preview does not save data; review it and click **Save item catalogue**. Saving replaces only that tender's catalogue with the shown rows.

The supplied CSV and known tender metadata are under **catalogues/**. Do not reuse SPMC/03/2026 item numbers for another tender without its own catalogue.

## Independent quotations

Use **Quotations** for freely entered products, quantities, units (MT, kg, pcs, etc.), and prices. These row numbers start at 1 and are unrelated to tender item numbers. No SPMC references or document fees enter quotation calculations.

A simple USECTA quotation starter is included. Upload your own edited quotation template for your preferred layout. Shipment details, packaging, payment terms, and notes are separate fields. Prices round to two decimal places before line totals are calculated. No tax or currency conversion is applied automatically.

## Word templates and layout

Upload a DOCX or DOTX in **Templates**, choose Tender or Quotation, and set the output scope. Every upload becomes a new version. Required fields can be selected at upload time. Keep USECTA's fixed company details as ordinary Word text; the app does not ask you to re-enter them.

Tender table: keep the header, then create three separate rows:

```text
{%tr for item in tender_items %}
{{ item.item_number }} | {{ item.description }} | {{ item.document_fee }}
{%tr endfor %}
```

The control tags belong in the first cell of their own rows. The middle row repeats with its original formatting. Optional quantity field: `{{ item.quantity_kg }}`.

Personnel list: use three separate paragraphs, separated with Enter:

```text
{%p for item in tender_items %}
{{ item.item_number }} – {{ item.description }}
{%p endfor %}
```

Single-item letters/forms use `{{ item_number }}` and `{{ item_description }}`. The agreement's `{{ agreement_item_names }}` comes from the selected item descriptions. Date fields include `document_date`, `agreement_effective_date`, `closing_date_long`, `closing_date_short`, `closing_time`, and `bid_valid_until`.

Quotations use `quotation_items` with `item.number`, `item.description`, `item.quantity`, `item.unit`, `item.unit_price`, and `item.total`. Totals are `subtotal` and `grand_total`. Do not use tender fields in quotation templates.

### What is preserved

The generator fills the existing Word package rather than reconstructing the document. Styles, numbering, themes, images, fixed headers/footers, relationships, and settings are retained byte-for-byte. Section settings (page size and margins), table widths, and repeated cell properties are checked against the supplied templates. Headers/footers that contain placeholders are rendered while keeping their existing formatting.

Bold, font family, and font size follow the formatting of each placeholder at its location, including inherited paragraph styles. Select the entire placeholder in Word to set its intended appearance. The app does not force one font size across a document or automatically shrink text. If a placeholder was given a different font size from its surrounding text, that difference is preserved.

Use `{{ supplier_name }}` to retain the entered capitalization and `{{ supplier_name | upper }}` for an uppercase occurrence. The supplied **Agency Agreement (formatting checked)** template uses uppercase for the supplier definition and the supplier signature heading, while retaining the entered case in the introductory paragraph. Its body inherits the Normal style's 11-point Times New Roman, and the signature heading keeps its existing bold Calibri formatting. Updating the file imports a new version; select that version for new agreements.

Longer supplier names, item descriptions, and item lists can legitimately change wrapping and pagination. PDF rendering also depends on fonts and LibreOffice's Word-layout support. The app does not shrink fonts, change margins, or force documents onto one page. For Word's own rendering, open the DOCX in Microsoft Word and export to PDF there.

The supplied collection and cover letters still contain the original "Agency Agreement" footer text, and the agreement contains typed page-count text. These were deliberately retained; correct them in Word if you want different footer wording, or use Word PAGE / NUMPAGES fields. The envelope closing time is now a placeholder rather than fixed at 10:00. Template corrections are listed in the downloadable check report.

## Storage, privacy, and backup

All live profiles, catalogues, templates, and saved runs are in the ignored **data/** folder beside the app. Generated downloads are held in memory. Original templates are never overwritten. Saved runs retain their own item/supplier input snapshot and exact template version IDs; later catalogue changes do not change that snapshot.

Back up the entire **data/** folder with the app stopped. The six supplied templates are included in GitHub for distribution. Later uploads, saved profiles, catalogues edited in the app, saved runs, and generated output files remain excluded from Git in **data/** and **exports/**. No company records are sent to an LLM or other application API. Dependency installation requires Internet access initially.

This application is intended for a trusted local user. Shared hosting, accounts, digital signatures, approval workflows, and automatic legal-clause changes are not included.

## Development and verification

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

`requirements.lock` pins the complete dependency set validated on the cloud machine. `requirements.txt` contains the application dependencies for normal local installation.

Check your company templates with sample data (never actual tender dates):

```bash
python scripts/check_templates.py company_templates --pdf
```

Omit `--pdf` if LibreOffice is unavailable. Outputs are clearly labelled SAMPLE_ONLY and saved under **data/review/sample_output/**. This validates small and 50-item lists, immutable style/media parts, section settings, and table properties.

For the Debian 13 cloud machine, `bash scripts/setup-cloud-pdf.sh` installs an authenticated rootless LibreOffice runtime under **data/pdf-runtime/**. Use the ordinary LibreOffice installer on Windows/macOS.
