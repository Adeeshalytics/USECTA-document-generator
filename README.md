# USECTA Document Generator

A local document generator for recurring company letters, agreements, and bids. Enter shared information once, select documents, and download editable DOCX files, PDFs, or a ZIP. No LLM, paid API, or API key is needed.

## Run on your computer

Requires Python 3.12 or newer. From this repository folder:

```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address 127.0.0.1
```

Open the address printed by Streamlit in your local browser. The application is intended for a single trusted user on a local computer. Shared hosting and user accounts are not included.

For PDF downloads, install the free **LibreOffice** application and make `libreoffice` or `soffice` available on your PATH. On Windows, add the LibreOffice `program` folder to PATH; on macOS, add `/Applications/LibreOffice.app/Contents/MacOS`. Restart the application after installation. On Ubuntu / Debian with administrator access:

```bash
sudo apt-get update
sudo apt-get install libreoffice-writer fonts-crosextra-carlito
```

DOCX downloads work without LibreOffice. PDF layouts depend on available fonts; check page breaks, tables, and signature blocks before sending.

## First document

1. Select the authorization, agreement, or bid covering letter.
2. Fill the company, recipient, personnel, and document fields. Required fields have an asterisk.
3. Add items when preparing a bid. Quantities must be positive. Unit prices round to two decimal places before line totals are calculated. No tax is applied automatically.
4. Click **Generate documents**, then download each file or the ZIP.
5. Review the generated document before signing or sending.

Save a company / personnel profile to reuse contact and signature details. Save a project to retain all fields, items, and selected template versions. Loading it restores those details. Saving the same project name creates a new record; saving the same profile name updates that profile.

## Use your own samples

The three starter documents are examples, not your company's final wording. In **Template library**, download a starter as an editing example, or prepare your own DOCX / DOTX sample in Word:

```text
Company: {{ company_name }}
Recipient: {{ customer_name }}
Authorized person: {{ authorized_person_name }}
Bid reference: {{ bid_reference }}
```

Keep existing logos, letterheads, styles, and signature areas. Replace variable text with placeholders. A sample PDF must first be recreated as a Word document; PDF upload and automatic placeholder detection from plain text are not included.

Upload the edited sample, give it a name, and choose which detected fields are required. Each upload becomes a separate template version; existing versions remain available. Simple custom fields such as `{{ purchase_order_number }}` automatically appear in the form. Field names should start with a letter and contain letters, numbers, or underscores. The app lists all built-in placeholders in the template library.

### Repeating item tables

Create a Word table with a header row followed by three rows. Put the loop-start tag in the first cell of the first row, the item placeholders in separate cells of the next row, and the loop-end tag in the first cell of the final row:

```text
{%tr for item in items %}
{{ item.number }} | {{ item.description }} | {{ item.quantity }} | {{ item.unit_price }} | {{ item.total }}
{%tr endfor %}
```

The tag rows disappear and the item row repeats. Below the table, use `{{ currency }} {{ grand_total }}`. Download the starter bid template for a working example. Optional wording can use `{% if delivery_terms %}...{% endif %}`. Use only trusted templates; complex Jinja expressions are unnecessary for this workflow.

## Storage and backup

The app creates an ignored `data/` folder beside `app.py`. `records.sqlite3` holds profiles and projects; `templates/` holds the Word templates. Downloads are generated in memory. Originals remain unchanged. Keep a backup of the **entire data folder**, with the app stopped while copying it. No company records are sent to an external API. Dependencies and LibreOffice installation require Internet access initially.

This first version does not include electronic signatures, approval workflows, taxes, currency conversion, or access controls.

## Development and cloud environment

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests exercise rendering, required fields, item calculations, DOTX uploads, persistence, and Streamlit interactions. The PDF test runs when LibreOffice is available; otherwise it is explicitly skipped.

`requirements.lock` pins the complete dependency set validated on the cloud machine. Install it with `python -m pip install -r requirements.lock` for that same development setup; `requirements.txt` contains the application dependencies for local installation.

For this Debian 13 cloud machine, `bash scripts/setup-cloud-pdf.sh` installs an authenticated, rootless LibreOffice runtime under `data/pdf-runtime/`. The app detects it automatically. This helper is specific to the cloud machine's operating system; use the normal LibreOffice installer on your own computer.
