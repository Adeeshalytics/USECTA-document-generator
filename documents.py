"""Local persistence, Word templates, and deterministic document generation."""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt
from docxtpl import DocxTemplate
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

DATA_DIR = Path(os.environ.get("USECTA_DATA_DIR", Path(__file__).resolve().parent / "data"))
FIELDS = {
    "company_name": "Company name", "company_address": "Company address",
    "company_email": "Company email", "company_phone": "Company phone",
    "customer_name": "Customer / recipient name", "customer_address": "Customer address",
    "document_date": "Document date", "bid_reference": "Bid reference",
    "authorized_person_name": "Authorized person name",
    "authorized_person_designation": "Authorized person designation",
    "authorized_person_id": "Authorized person ID / reference",
    "signatory_name": "Signatory name", "signatory_designation": "Signatory designation",
    "agreement_subject": "Agreement subject", "agreement_terms": "Agreement terms",
    "delivery_terms": "Delivery terms", "currency": "Currency",
    "bid_valid_until": "Bid acceptance validity date (set in Tenders & items)",
    "tender_items": "Selected tender item list", "agreement_item_names": "Selected agreement items",
    "quotation_items": "Quotation item list",
}
COMPUTED = {"items", "grand_total"}
CENT = Decimal("0.01")


class Store:
    def __init__(self, root: Path = DATA_DIR):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.templates_dir = self.root / "templates"
        self.templates_dir.mkdir(exist_ok=True)
        self.db = self.root / "records.sqlite3"
        with self.connect() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS profiles (
                    name TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, payload TEXT NOT NULL,
                    created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS templates (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, filename TEXT NOT NULL,
                    required TEXT NOT NULL, created_at TEXT NOT NULL);
            """)
            columns = {r["name"] for r in con.execute("PRAGMA table_info(templates)")}
            for column, default in [("workflow", "legacy"), ("scope", "batch")]:
                if column not in columns:
                    con.execute(f"ALTER TABLE templates ADD COLUMN {column} TEXT NOT NULL DEFAULT '{default}'")
            con.executescript("""
                CREATE TABLE IF NOT EXISTS tenders (reference TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tender_items (
                    reference TEXT NOT NULL, item_number TEXT NOT NULL, description TEXT NOT NULL,
                    document_fee TEXT NOT NULL, PRIMARY KEY (reference, item_number));
                CREATE TABLE IF NOT EXISTS suppliers (id TEXT PRIMARY KEY, name TEXT NOT NULL, payload TEXT NOT NULL);
            """)
            item_columns = {r["name"] for r in con.execute("PRAGMA table_info(tender_items)")}
            if "quantity_kg" not in item_columns:
                con.execute("ALTER TABLE tender_items ADD COLUMN quantity_kg TEXT NOT NULL DEFAULT ''")

    def connect(self):
        con = sqlite3.connect(self.db)
        con.row_factory = sqlite3.Row
        return con

    def profiles(self):
        with self.connect() as con:
            return {r["name"]: json.loads(r["payload"]) for r in con.execute("SELECT * FROM profiles ORDER BY name")}

    def save_profile(self, name, payload):
        if not name.strip():
            raise ValueError("Give the profile a name.")
        with self.connect() as con:
            con.execute("INSERT INTO profiles VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET payload=excluded.payload", (name.strip(), json.dumps(payload)))

    def records(self):
        with self.connect() as con:
            return [dict(r) for r in con.execute("SELECT * FROM records ORDER BY created_at DESC")]

    def save_record(self, name, payload):
        if not name.strip():
            raise ValueError("Give the project a name.")
        key = uuid.uuid4().hex
        with self.connect() as con:
            con.execute("INSERT INTO records VALUES (?, ?, ?, ?)", (key, name.strip(), json.dumps(payload), datetime.now(timezone.utc).isoformat()))
        return key

    def templates(self):
        with self.connect() as con:
            return [dict(r) | {"required": json.loads(r["required"])} for r in con.execute("SELECT * FROM templates ORDER BY name")]

    def template_path(self, template):
        return self.templates_dir / template["filename"]

    def add_template(self, name, content, required=(), key=None, workflow="legacy", scope="batch"):
        if not name.strip():
            raise ValueError("Give the template a name.")
        validate_word(content)
        variables = template_variables(content)
        for field in variables - set(FIELDS) - COMPUTED:
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", field):
                raise ValueError(f"Unsupported field name: {field}")
        if set(required) - variables:
            raise ValueError("Required fields must appear in the template.")
        key = key or uuid.uuid4().hex
        path = self.templates_dir / f"{key}.docx"
        path.write_bytes(content)
        with self.connect() as con:
            con.execute("INSERT INTO templates (id, name, filename, required, created_at, workflow, scope) VALUES (?, ?, ?, ?, ?, ?, ?)", (key, name.strip(), path.name, json.dumps(list(required)), datetime.now(timezone.utc).isoformat(), workflow, scope))
        return key

    def set_template_usage(self, key, workflow, scope):
        if workflow not in {"legacy", "tender", "quotation"} or scope not in {"batch", "item", "supplier", "tender"}:
            raise ValueError("Choose a supported document type and scope.")
        with self.connect() as con:
            con.execute("UPDATE templates SET workflow=?, scope=? WHERE id=?", (workflow, scope, key))

    def tenders(self):
        with self.connect() as con:
            return {r["reference"]: json.loads(r["payload"]) for r in con.execute("SELECT * FROM tenders ORDER BY reference")}

    def save_tender(self, reference, payload):
        from workflows import validate_tender
        reference = reference.strip()
        validate_tender(reference, payload)
        with self.connect() as con:
            con.execute("INSERT INTO tenders VALUES (?, ?) ON CONFLICT(reference) DO UPDATE SET payload=excluded.payload", (reference, json.dumps(payload)))

    def catalog(self, reference):
        with self.connect() as con:
            return [dict(r) for r in con.execute("SELECT item_number, description, document_fee, quantity_kg FROM tender_items WHERE reference=? ORDER BY length(item_number), item_number", (reference,))]

    def save_catalog(self, reference, rows):
        from workflows import validate_catalog
        cleaned = validate_catalog(rows)
        with self.connect() as con:
            if not con.execute("SELECT 1 FROM tenders WHERE reference=?", (reference,)).fetchone():
                raise ValueError("Save this tender before adding its item catalogue.")
            con.execute("DELETE FROM tender_items WHERE reference=?", (reference,))
            con.executemany("INSERT INTO tender_items (reference,item_number,description,document_fee,quantity_kg) VALUES (?, ?, ?, ?, ?)", [(reference, r["item_number"], r["description"], r["document_fee"], r["quantity_kg"]) for r in cleaned])

    def suppliers(self):
        with self.connect() as con:
            return {r["id"]: json.loads(r["payload"]) for r in con.execute("SELECT * FROM suppliers ORDER BY name")}

    def save_supplier(self, payload, key=None):
        if not payload.get("supplier_name", "").strip():
            raise ValueError("Enter the supplier name.")
        key = key or uuid.uuid4().hex
        with self.connect() as con:
            con.execute("INSERT INTO suppliers VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, payload=excluded.payload", (key, payload["supplier_name"].strip(), json.dumps(payload)))
        return key


def validate_word(content):
    if len(content) > 10 * 1024 * 1024:
        raise ValueError("Templates must be smaller than 10 MB.")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if sum(x.file_size for x in archive.infolist()) > 50 * 1024 * 1024:
                raise ValueError("The expanded template is too large.")
            if "word/document.xml" not in archive.namelist():
                raise ValueError("Upload a valid DOCX or DOTX Word document.")
            if any("vbaproject" in x.lower() for x in archive.namelist()):
                raise ValueError("Macro-enabled templates are not supported.")
    except zipfile.BadZipFile as exc:
        raise ValueError("Upload a valid DOCX or DOTX Word document.") from exc


def normalize_word(content):
    """Turn a DOTX package into a DOCX package without altering its layout."""
    validate_word(content)
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(content)) as src, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as dest:
        for member in src.infolist():
            data = src.read(member.filename)
            if member.filename == "[Content_Types].xml":
                data = data.replace(b"application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml", b"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml")
            dest.writestr(member, data)
    return output.getvalue()


def template_variables(content):
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for name in archive.namelist():
            if name.startswith("word/") and name.endswith(".xml"):
                from lxml import etree
                root = etree.fromstring(archive.read(name))
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                for paragraph in root.findall(".//w:p", ns):
                    text = "".join(paragraph.xpath(".//w:t/text()", namespaces=ns))
                    if re.search(r"(?<!\{)\{\s*[A-Za-z_]\w*\s*\}\}", text):
                        raise ValueError("A placeholder is missing its opening brace. Use {{ field_name }}.")
    tpl = DocxTemplate(io.BytesIO(normalize_word(content)))
    return tpl.get_undeclared_template_variables(jinja_env=SandboxedEnvironment())


def money(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0:
            raise ValueError("Amounts and quantities must be finite and non-negative.")
        return number
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Enter valid numeric quantities and prices.") from exc


def build_context(fields, rows):
    context = {key: str(value or "") for key, value in fields.items()}
    items = []
    total = Decimal(0)
    for row in rows:
        description = str(row.get("description") or "").strip()
        if not description:
            if money(row.get("quantity", 0)) or money(row.get("unit_price", 0)):
                raise ValueError("Each priced item needs a description.")
            continue
        quantity = money(row.get("quantity", 0))
        if quantity <= 0:
            raise ValueError(f"Quantity must be greater than zero for {description}.")
        price = money(row.get("unit_price", 0)).quantize(CENT, rounding=ROUND_HALF_UP)
        subtotal = (quantity * price).quantize(CENT, rounding=ROUND_HALF_UP)
        total += subtotal
        items.append({"number": len(items) + 1, "description": description,
                      "quantity": format(quantity.normalize(), "f"), "unit_price": f"{price:,.2f}", "total": f"{subtotal:,.2f}"})
    context.update(items=items, grand_total=f"{total:,.2f}")
    return context


def render_document(content, context, required=()):
    missing = [x for x in required if not context.get(x) or (isinstance(context[x], str) and not context[x].strip())]
    if missing:
        raise ValueError("Complete required fields: " + ", ".join(FIELDS.get(x, x) for x in missing))
    source = normalize_word(content)
    template = DocxTemplate(io.BytesIO(source))
    template.render(context, jinja_env=SandboxedEnvironment(undefined=StrictUndefined), autoescape=True)
    output = io.BytesIO()
    template.save(output)
    # python-docx reserializes many unrelated package parts on save. Our context
    # contains plain values only, so filling fields needs no new styles, images,
    # relationships, or settings. Keep those original parts byte-for-byte.
    preserved = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(source)) as original, zipfile.ZipFile(io.BytesIO(output.getvalue())) as rendered, zipfile.ZipFile(preserved, "w", zipfile.ZIP_DEFLATED) as final:
        for member in original.infolist():
            data = original.read(member.filename)
            replace = member.filename == "word/document.xml"
            if re.fullmatch(r"word/(header\d*|footer\d*|footnotes)\.xml", member.filename):
                from lxml import etree
                xml = etree.fromstring(data)
                text = "".join(xml.xpath("//*[local-name()='t']/text()"))
                replace = "{{" in text or "{%" in text
            if replace and member.filename in rendered.namelist():
                data = rendered.read(member.filename)
            final.writestr(member, data)
    return preserved.getvalue()


def pdf_available():
    root = Path(__file__).resolve().parent
    candidates = [os.environ.get("USECTA_PDF_EXECUTABLE"),
                  root / "runtime/libreoffice/program/soffice.exe",
                  root / "LibreOfficePortable/App/libreoffice/program/soffice.exe",
                  DATA_DIR / "pdf-runtime/bin/libreoffice"]
    for folder in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if folder:
            candidates.append(Path(folder) / "LibreOffice/program/soffice.exe")
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    return shutil.which("libreoffice") or shutil.which("soffice")


def convert_pdfs(documents):
    """Convert Word documents in batches so LibreOffice starts fewer times."""
    if not documents:
        return {}
    executable = pdf_available()
    if not executable:
        raise ValueError("PDF export needs LibreOffice. Install it, or download DOCX and export to PDF in Word.")
    converted = {}
    entries = list(documents.items())
    # Keep Windows command lines short and give each batch an isolated profile.
    for offset in range(0, len(entries), 20):
        batch = entries[offset:offset + 20]
        with tempfile.TemporaryDirectory(prefix="usecta-pdf-") as temp:
            root = Path(temp)
            sources = []
            for index, (_, content) in enumerate(batch):
                source = root / f"document-{index}.docx"
                source.write_bytes(content)
                sources.append(source)
            command = [executable, f"-env:UserInstallation={(root / 'profile').as_uri()}",
                       "--headless", "--convert-to", "pdf", "--outdir", str(root)]
            try:
                result = subprocess.run(command + [str(source) for source in sources],
                                        capture_output=True, timeout=max(90, 30 * len(batch)))
            except subprocess.TimeoutExpired:
                raise ValueError("PDF conversion took too long. Try fewer documents at a time.") from None
            if result.returncode:
                raise ValueError("LibreOffice could not convert these documents. Download DOCX and check the layout in Word.")
            for (name, _), source in zip(batch, sources):
                target = source.with_suffix('.pdf')
                if not target.exists():
                    raise ValueError(f"LibreOffice could not generate the PDF for {name}.")
                content = target.read_bytes()
                if not content.startswith(b'%PDF-'):
                    raise ValueError(f"LibreOffice generated an invalid PDF for {name}.")
                converted[name[:-5] + '.pdf'] = content
    return converted


def convert_pdf(content):
    return convert_pdfs({'document.docx': content})['document.pdf']


def filename(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")[:80] or "document"


def make_zip(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


def create_starters(store):
    """Create examples once; they are starting points for the user's wording."""
    existing = {t["id"] for t in store.templates()}
    specs = [
        ("starter-authorization", "Authorization letter", "AUTHORIZATION LETTER", [
            "To: {{ customer_name }}", "{{ customer_address }}", "Reference: {{ bid_reference }}",
            "We, {{ company_name }}, authorize {{ authorized_person_name }}, {{ authorized_person_designation }} (ID/reference: {{ authorized_person_id }}), to represent our company in connection with the above reference.",
            "{{ delivery_terms }}"], ["company_name", "customer_name", "authorized_person_name", "authorized_person_designation", "bid_reference", "signatory_name"]),
        ("starter-agreement", "Agreement letter", "AGREEMENT LETTER", [
            "To: {{ customer_name }}", "{{ customer_address }}", "Subject: {{ agreement_subject }}",
            "This letter records the agreement between {{ company_name }} and {{ customer_name }} regarding {{ agreement_subject }}.",
            "Agreed terms", "{{ agreement_terms }}"], ["company_name", "customer_name", "agreement_subject", "agreement_terms", "signatory_name"]),
        ("starter-bid", "Bid covering letter", "BID COVERING LETTER", [
            "To: {{ customer_name }}", "{{ customer_address }}", "Bid reference: {{ bid_reference }}",
            "On behalf of {{ company_name }}, we submit the following items for your consideration.",
            "Delivery terms: {{ delivery_terms }}"], ["company_name", "customer_name", "bid_reference", "items", "signatory_name"]),
    ]
    for key, name, heading, paragraphs, required in specs:
        if key in existing:
            continue
        doc = Document()
        doc.sections[0].top_margin = Inches(0.75)
        normal = doc.styles["Normal"]
        normal.font.name = "Calibri"
        normal.font.size = Pt(11)
        doc.add_heading("{{ company_name }}", 0)
        doc.add_paragraph("{{ company_address }}\n{{ company_email }} | {{ company_phone }}")
        doc.add_paragraph("Date: {{ document_date }}")
        doc.add_heading(heading, 1)
        for paragraph in paragraphs:
            doc.add_paragraph(paragraph)
        if key == "starter-bid":
            table = doc.add_table(rows=1, cols=5)
            table.style = "Table Grid"
            for cell, label in zip(table.rows[0].cells, ["No.", "Description", "Quantity", "Unit price", "Total"]):
                cell.text = label
            table.add_row().cells[0].text = "{%tr for item in items %}"
            for cell, field in zip(table.add_row().cells, ["number", "description", "quantity", "unit_price", "total"]):
                cell.text = "{{ item." + field + " }}"
            table.add_row().cells[0].text = "{%tr endfor %}"
            doc.add_paragraph("Grand total: {{ currency }} {{ grand_total }}")
        doc.add_paragraph("Yours faithfully,\n\n________________________\n{{ signatory_name }}\n{{ signatory_designation }}\n{{ company_name }}")
        output = io.BytesIO()
        doc.save(output)
        store.add_template(name, output.getvalue(), required, key)
