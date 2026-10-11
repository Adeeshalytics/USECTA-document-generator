"""Local persistence, Word templates, and deterministic document generation."""
from __future__ import annotations

import io
import os
import json
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
from functools import lru_cache
from contextlib import contextmanager

from docx import Document
from docx.shared import Inches, Pt
from docxtpl import DocxTemplate
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from desktop_paths import asset_root, offline_mode, workspace_root, workspace_lock

DATA_DIR = workspace_root() if offline_mode() else Path(__file__).resolve().parent / "data"
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
                CREATE INDEX IF NOT EXISTS records_created ON records(created_at DESC);
            """)
            item_columns = {r["name"] for r in con.execute("PRAGMA table_info(tender_items)")}
            if "quantity_kg" not in item_columns:
                con.execute("ALTER TABLE tender_items ADD COLUMN quantity_kg TEXT NOT NULL DEFAULT ''")

    @contextmanager
    def connect(self):
        with workspace_lock(str(self.root.resolve())):
            con = sqlite3.connect(self.db, timeout=15)
            con.row_factory = sqlite3.Row
            try:
                with con:
                    yield con
            finally:
                con.close()

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

    def record_summaries(self, search="", limit=50):
        with self.connect() as con:
            return [dict(r) for r in con.execute(
                "SELECT id,name,created_at FROM records WHERE instr(lower(name),lower(?)) > 0 "
                "ORDER BY created_at DESC LIMIT ?", (search, limit))]

    def record(self, key):
        with self.connect() as con:
            row = con.execute("SELECT * FROM records WHERE id=?", (key,)).fetchone()
            if row is None:
                raise ValueError("Saved run not found.")
            return dict(row)

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
        if not re.fullmatch(r"[A-Za-z0-9_-]+\.docx", template["filename"]):
            raise ValueError("Invalid stored template filename.")
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
        if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
            raise ValueError("Invalid template ID.")
        if workflow not in {"legacy", "tender", "quotation"} or scope not in {"batch", "item", "supplier", "tender"}:
            raise ValueError("Choose a supported document type and scope.")
        path = self.templates_dir / f"{key}.docx"
        with self.connect() as con:
            existing = con.execute("SELECT filename FROM templates WHERE id=?", (key,)).fetchone()
            if existing:
                if path.read_bytes() != content:
                    raise ValueError("This template version already contains different content.")
                return key
            with tempfile.NamedTemporaryFile(dir=self.templates_dir, delete=False) as output:
                temporary = Path(output.name)
                output.write(content)
            try:
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
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

    def seed_tender(self, reference, payload, rows):
        from workflows import validate_catalog, validate_tender
        validate_tender(reference, payload)
        cleaned = validate_catalog(rows)
        with self.connect() as con:
            if con.execute("SELECT 1 FROM tenders WHERE reference=?", (reference,)).fetchone():
                return
            con.execute("INSERT INTO tenders VALUES (?,?)", (reference, json.dumps(payload)))
            con.executemany("INSERT INTO tender_items (reference,item_number,description,document_fee,quantity_kg) VALUES (?,?,?,?,?)", [(reference, r["item_number"], r["description"], r["document_fee"], r["quantity_kg"]) for r in cleaned])

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


@lru_cache(maxsize=32)
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
    return frozenset(tpl.get_undeclared_template_variables(jinja_env=SandboxedEnvironment()))


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
    # Retain compatibility with existing source/USB desktop installations.
    for candidate in [os.environ.get("USECTA_PDF_EXECUTABLE"),
                      asset_root() / "runtime/libreoffice/program/soffice.exe",
                      asset_root() / "LibreOfficePortable/App/libreoffice/program/soffice.exe"]:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    bundled = asset_root() / "pdf-runtime" / "program" / "soffice.exe"
    if bundled.is_file():
        return str(bundled)
    developer_runtime = asset_root() / "vendor" / "pdf-runtime" / "program" / "soffice.exe"
    if developer_runtime.is_file():
        return str(developer_runtime)
    for base in [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)")]:
        if base:
            candidate = Path(base) / "LibreOffice" / "program" / "soffice.exe"
            if candidate.is_file():
                return str(candidate)
    local = DATA_DIR / "pdf-runtime" / "bin" / "libreoffice"
    return shutil.which("libreoffice") or shutil.which("soffice") or (str(local) if local.is_file() else None)


def convert_pdf(content):
    return convert_pdfs({"document.docx": content})["document.pdf"]


def convert_pdfs(files):
    """Convert a batch in one isolated LibreOffice process, without a console."""
    if not files:
        return {}
    executable = pdf_available()
    if not executable:
        raise ValueError("PDF export needs LibreOffice. Install it, or download DOCX and export to PDF in Word.")
    with tempfile.TemporaryDirectory(prefix="usecta-pdf-") as temp:
        root = Path(temp)
        profile = root / "profile" / "user"
        profile.mkdir(parents=True)
        # No macros or linked-content refresh in the unattended converter.
        (profile / "registrymodifications.xcu").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<oor:items xmlns:oor="http://openoffice.org/2001/registry">'
            '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
            '<prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>'
            '<item oor:path="/org.openoffice.Office.Writer/Content/Update">'
            '<prop oor:name="Link" oor:op="fuse"><value>0</value></prop></item>'
            '</oor:items>', encoding="utf-8")
        sources = []
        for name, content in files.items():
            if Path(name).name != name or not name.endswith(".docx"):
                raise ValueError("Invalid PDF input filename.")
            source = root / name
            source.write_bytes(content)
            sources.append(str(source))
        # Limit batch size so Windows command-line length stays bounded.
        for start in range(0, len(sources), 20):
            try:
                result = subprocess.run([executable, f"-env:UserInstallation={(root / 'profile').as_uri()}", "--headless", "--norestore", "--nodefault", "--convert-to", "pdf", "--outdir", str(root), *sources[start:start + 20]], capture_output=True, timeout=180,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            except subprocess.TimeoutExpired as exc:
                raise ValueError("PDF conversion timed out. Your DOCX files are still available.") from exc
            if result.returncode:
                raise ValueError("LibreOffice could not convert this batch. Your DOCX files are still available.")
        targets = {name[:-5] + ".pdf": root / (name[:-5] + ".pdf") for name in files}
        if not all(target.is_file() for target in targets.values()):
            raise ValueError("LibreOffice could not convert this document. Download the DOCX and check its layout in Word.")
        converted = {name: target.read_bytes() for name, target in targets.items()}
        if not all(content.startswith(b"%PDF-") for content in converted.values()):
            raise ValueError("LibreOffice generated an invalid PDF. Your DOCX files are still available.")
        return converted


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
