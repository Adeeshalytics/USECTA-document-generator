"""Validated offline backups and company-record transfer packages.

Archives contain logical records, not executable database files. No ZIP member
is ever extracted using its supplied path. Restores replace the database only
after a complete staged workspace has passed validation.
"""
import hashlib
import io
import json
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from desktop_paths import VERSION, workspace_lock
from documents import Store, validate_word, template_variables, filename
from workflows import validate_catalog, validate_tender

FORMAT = "usecta-workspace"
MAX_ARCHIVE = 200 * 1024 * 1024
MAX_EXPANDED = 300 * 1024 * 1024


def export_workspace(store, shared=False):
    with workspace_lock(str(store.root.resolve())):
        templates = store.templates()
        payload = {"format": FORMAT, "version": 1, "app_version": VERSION,
                   "kind": "share" if shared else "backup",
                   "created_at": datetime.now(timezone.utc).isoformat(),
                   "tenders": store.tenders(), "suppliers": store.suppliers(),
                   "catalogues": {key: store.catalog(key) for key in store.tenders()},
                   "profiles": {} if shared else store.profiles(),
                   "records": [] if shared else store.records(), "templates": []}
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for template in templates:
                content = store.template_path(template).read_bytes()
                digest = hashlib.sha256(content).hexdigest()
                member = "templates/" + digest + ".docx"
                if member not in archive.namelist():
                    archive.writestr(member, content)
                payload["templates"].append(template | {"archive_path": member, "sha256": digest})
            archive.writestr("workspace.json", json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        if len(output.getvalue()) > MAX_ARCHIVE:
            raise ValueError("Workspace is too large for an in-app backup. Contact support for an archive export.")
        return output.getvalue()


def inspect_archive(content):
    if len(content) > MAX_ARCHIVE:
        raise ValueError("Backup or share packages must be smaller than 200 MB.")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > 10000 or sum(m.file_size for m in members) > MAX_EXPANDED:
                raise ValueError("The expanded archive is too large.")
            names = [m.filename for m in members]
            if len(names) != len(set(names)) or "workspace.json" not in names:
                raise ValueError("Not a valid USECTA backup or share package.")
            if archive.getinfo("workspace.json").file_size > 30 * 1024 * 1024:
                raise ValueError("Archive metadata is too large.")
            payload = json.loads(archive.read("workspace.json"))
            if payload.get("format") != FORMAT or payload.get("version") != 1 or payload.get("kind") not in {"backup", "share"}:
                raise ValueError("Unsupported USECTA archive format.")
            for key in ["tenders", "suppliers", "catalogues", "profiles"]:
                if not isinstance(payload.get(key), dict):
                    raise ValueError("Invalid archive records.")
            if not isinstance(payload.get("templates"), list) or not isinstance(payload.get("records"), list):
                raise ValueError("Invalid archive records.")
            for ref, tender in payload["tenders"].items():
                validate_tender(ref, tender)
            for ref, rows in payload["catalogues"].items():
                if ref not in payload["tenders"]:
                    raise ValueError("Catalogue has no associated tender.")
                if rows:
                    validate_catalog(rows)
            for supplier in payload["suppliers"].values():
                if not isinstance(supplier, dict) or not supplier.get("supplier_name", "").strip():
                    raise ValueError("Invalid supplier record.")
            ids, allowed_members = set(), {"workspace.json"}
            template_files = {}
            for template in payload["templates"]:
                key, member = template["id"], template["archive_path"]
                if key in ids or filename(key) != key or not key:
                    raise ValueError("Invalid or duplicate template ID.")
                ids.add(key)
                if member != "templates/" + template["sha256"] + ".docx":
                    raise ValueError("Invalid template archive path.")
                allowed_members.add(member)
                data = archive.read(member)
                if hashlib.sha256(data).hexdigest() != template["sha256"]:
                    raise ValueError("Template checksum failed.")
                validate_word(data)
                variables = template_variables(data)
                if set(template["required"]) - variables:
                    raise ValueError("Template required fields do not match its placeholders.")
                if template["workflow"] not in {"legacy", "tender", "quotation"} or template["scope"] not in {"batch", "item", "supplier", "tender"}:
                    raise ValueError("Invalid template workflow or scope.")
                template_files[key] = data
            if set(names) != allowed_members:
                raise ValueError("Archive contains unexpected files.")
            record_ids = set()
            for record in payload["records"]:
                if record["id"] in record_ids:
                    raise ValueError("Duplicate saved run ID.")
                record_ids.add(record["id"])
                saved = json.loads(record["payload"])
                for job in saved.get("jobs", []):
                    if job["template_id"] not in ids:
                        raise ValueError("A saved run refers to a missing template.")
            return payload, template_files
    except (zipfile.BadZipFile, KeyError, TypeError, AttributeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid or damaged USECTA archive.") from exc


def archive_summary(payload):
    return {"Package": payload["kind"], "Tenders": len(payload["tenders"]),
            "Suppliers": len(payload["suppliers"]), "Templates": len(payload["templates"]),
            "Saved runs": len(payload["records"])}


def save_automatic_backup(store, label="automatic"):
    folder = store.root / "backups"
    folder.mkdir(exist_ok=True)
    path = folder / (datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + label + "-" + uuid.uuid4().hex[:8] + ".zip")
    path.write_bytes(export_workspace(store))
    return path


def restore_workspace(store, content):
    payload, files = inspect_archive(content)
    if payload["kind"] != "backup":
        raise ValueError("Use Import company records for a share package.")
    with workspace_lock(str(store.root.resolve())):
        with tempfile.TemporaryDirectory(prefix="restore-", dir=store.root) as temporary:
            staged = Store(Path(temporary))
            for template in payload["templates"]:
                staged.add_template(template["name"], files[template["id"]], template["required"], template["id"], template["workflow"], template["scope"])
            with staged.connect() as con:
                for template in payload["templates"]:
                    con.execute("UPDATE templates SET created_at=? WHERE id=?", (template["created_at"], template["id"]))
                for record in payload["records"]:
                    con.execute("INSERT INTO records VALUES (?,?,?,?)", (record["id"], record["name"], record["payload"], record["created_at"]))
            for name, profile in payload["profiles"].items():
                staged.save_profile(name, profile)
            for key, supplier in payload["suppliers"].items():
                staged.save_supplier(supplier, key)
            for ref, tender in payload["tenders"].items():
                staged.save_tender(ref, tender)
                if payload["catalogues"].get(ref):
                    staged.save_catalog(ref, payload["catalogues"][ref])
            # Different content uses different names, leaving the old workspace
            # intact even if the final database replacement fails.
            with staged.connect() as con:
                for template in staged.templates():
                    data = staged.template_path(template).read_bytes()
                    name = "restored_" + hashlib.sha256(data).hexdigest() + ".docx"
                    target = store.templates_dir / name
                    if not target.exists():
                        temp_path = Path(temporary) / name
                        temp_path.write_bytes(data)
                        temp_path.replace(target)
                    con.execute("UPDATE templates SET filename=? WHERE id=?", (name, template["id"]))
            safety = save_automatic_backup(store, "before-restore")
            staged.db.replace(store.db)
        template_variables.cache_clear()
        return safety


def import_company_records(store, content, replace=False):
    payload, files = inspect_archive(content)
    if payload["kind"] != "share":
        raise ValueError("Use Restore workspace for a backup package.")
    with workspace_lock(str(store.root.resolve())):
        save_automatic_backup(store, "before-import")
        # Create all immutable template files first. One transaction changes
        # metadata and company records; a failure cannot partially import rows.
        prepared = []
        for template in payload["templates"]:
            data = files[template["id"]]
            identity = data + json.dumps([template["name"], template["required"], template["workflow"], template["scope"]], sort_keys=True).encode()
            key = "shared-" + hashlib.sha256(identity).hexdigest()[:24]
            target = store.templates_dir / (key + ".docx")
            if not target.exists():
                with tempfile.NamedTemporaryFile(dir=store.templates_dir, delete=False) as output:
                    temporary = Path(output.name)
                    output.write(data)
                temporary.replace(target)
            prepared.append((key, template["name"], target.name, json.dumps(template["required"]), template["created_at"], template["workflow"], template["scope"]))
        counts = {"tenders": 0, "suppliers": 0, "templates": 0}
        with store.connect() as con:
            for ref, tender in payload["tenders"].items():
                exists = con.execute("SELECT 1 FROM tenders WHERE reference=?", (ref,)).fetchone()
                if exists and not replace:
                    continue
                con.execute("INSERT INTO tenders VALUES (?,?) ON CONFLICT(reference) DO UPDATE SET payload=excluded.payload", (ref, json.dumps(tender)))
                con.execute("DELETE FROM tender_items WHERE reference=?", (ref,))
                rows = validate_catalog(payload["catalogues"][ref]) if payload["catalogues"].get(ref) else []
                con.executemany("INSERT INTO tender_items VALUES (?,?,?,?,?)", [(ref, r["item_number"], r["description"], r["document_fee"], r["quantity_kg"]) for r in rows])
                counts["tenders"] += 1
            for key, supplier in payload["suppliers"].items():
                found = con.execute("SELECT id FROM suppliers WHERE id=? OR lower(name)=lower(?)", (key, supplier["supplier_name"])).fetchone()
                if found and not replace:
                    continue
                actual_key = found["id"] if found else key
                con.execute("INSERT INTO suppliers VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,payload=excluded.payload", (actual_key, supplier["supplier_name"], json.dumps(supplier)))
                counts["suppliers"] += 1
            for row in prepared:
                result = con.execute("INSERT OR IGNORE INTO templates (id,name,filename,required,created_at,workflow,scope) VALUES (?,?,?,?,?,?,?)", row)
                counts["templates"] += result.rowcount
        return counts
