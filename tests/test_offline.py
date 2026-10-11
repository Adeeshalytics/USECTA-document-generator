import io
import json
import zipfile
from pathlib import Path
import subprocess
import sys
import os
import time

import pytest
from streamlit.testing.v1 import AppTest

import documents
from documents import Store, template_variables
from workflows import prepare_workspace, choose_items, tender_context, tender_jobs, generate_files
from workspace_archive import export_workspace, inspect_archive, restore_workspace, import_company_records

APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def workspace(tmp_path):
    store = Store(tmp_path / "source")
    prepare_workspace(store)
    store.save_supplier({"supplier_name": "Original Supplier", "supplier_country": "China", "supplier_address": "Example Address", "supplier_registration_number": "123"}, "supplier-one")
    return store


def test_backup_restore_regenerates_exact_template_and_snapshot(workspace, tmp_path):
    rows = choose_items(workspace, "SPMC/03/2026", ["2", "15"])
    supplier = workspace.suppliers()["supplier-one"]
    tender = workspace.tenders()["SPMC/03/2026"] | {"bid_valid_until": "2027-02-03"}
    context = tender_context("SPMC/03/2026", tender, rows, supplier, "2026-10-10", "2026-10-10")
    ids = [t["id"] for t in workspace.templates() if t["workflow"] == "tender"]
    jobs = tender_jobs(workspace, ids, context)
    original = generate_files(workspace, jobs)
    workspace.save_record("Original tender", {"jobs": jobs})
    content = export_workspace(workspace)
    restored = Store(tmp_path / "destination")
    restored.save_supplier({"supplier_name": "Before Restore"})
    safety = restore_workspace(restored, content)
    assert inspect_archive(safety.read_bytes())[0]["suppliers"]
    assert restored.suppliers() == workspace.suppliers()
    assert restored.templates() == [t | {"filename": "restored_" + __import__("hashlib").sha256(workspace.template_path(t).read_bytes()).hexdigest() + ".docx"} for t in workspace.templates()]
    saved = json.loads(restored.records()[0]["payload"])
    assert generate_files(restored, saved["jobs"]) == original


def test_share_import_conflicts_and_idempotency(workspace, tmp_path):
    content = export_workspace(workspace, shared=True)
    target = Store(tmp_path / "other")
    target.save_supplier({"supplier_name": "Original Supplier", "supplier_country": "Keep this"}, "supplier-one")
    target.save_record("Private history", {})
    counts = import_company_records(target, content)
    assert counts["suppliers"] == 0
    assert target.suppliers()["supplier-one"]["supplier_country"] == "Keep this"
    assert len(target.records()) == 1
    assert import_company_records(target, content)["templates"] == 0
    import_company_records(target, content, replace=True)
    assert target.suppliers()["supplier-one"]["supplier_country"] == "China"
    assert len(target.records()) == 1


@pytest.mark.parametrize("damage", ["unexpected", "checksum", "duplicate", "invalid_catalogue"])
def test_archive_rejection_leaves_workspace_unchanged(workspace, damage):
    source = export_workspace(workspace)
    dest = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(source)) as incoming, zipfile.ZipFile(dest, "w") as outgoing:
        for entry in incoming.infolist():
            data = incoming.read(entry.filename)
            if damage == "checksum" and entry.filename.startswith("templates/"):
                data = data + b"corrupt"
            if damage == "invalid_catalogue" and entry.filename == "workspace.json":
                payload = json.loads(data)
                payload["catalogues"]["SPMC/03/2026"][0]["document_fee"] = "-1"
                data = json.dumps(payload).encode()
            outgoing.writestr(entry, data)
        if damage == "unexpected":
            outgoing.writestr("../../outside.txt", b"bad")
        if damage == "duplicate":
            outgoing.writestr("workspace.json", incoming.read("workspace.json"))
    before = workspace.suppliers(), workspace.catalog("SPMC/03/2026"), workspace.templates()
    with pytest.raises(ValueError):
        restore_workspace(workspace, dest.getvalue())
    assert (workspace.suppliers(), workspace.catalog("SPMC/03/2026"), workspace.templates()) == before


def test_template_versions_cannot_be_overwritten(workspace):
    template = workspace.templates()[0]
    before = workspace.template_path(template).read_bytes()
    assert workspace.add_template("Same bytes", before, key=template["id"]) == template["id"]
    with pytest.raises(ValueError, match="different content"):
        workspace.add_template("Changed", before + b"different", key=template["id"])
    assert workspace.template_path(template).read_bytes() == before


def test_lazy_navigation_preserves_inputs_and_skips_template_reads(workspace, monkeypatch):
    monkeypatch.setattr(documents, "Store", lambda: workspace)
    app = AppTest.from_file(APP, default_timeout=20).run()
    app.radio(key="page").set_value("Quotations").run()
    app.text_input(key="quotation_number").set_value("DRAFT-123").run()
    app.text_input(key="quote_customer_name").set_value("Draft Customer").run()
    monkeypatch.setattr(workspace, "template_path", lambda *_: (_ for _ in ()).throw(AssertionError("Hidden templates must not be read")))
    app.radio(key="page").set_value("Suppliers").run()
    assert not app.exception
    assert not any(field.key == "quotation_number" for field in app.text_input)
    monkeypatch.undo()
    app.radio(key="page").set_value("Quotations").run()
    assert not app.exception
    assert app.text_input(key="quotation_number").value == "DRAFT-123"
    assert app.text_input(key="quote_customer_name").value == "Draft Customer"


def test_offline_mode_ignores_cloud_credentials(workspace, monkeypatch):
    monkeypatch.setenv("USECTA_OFFLINE", "1")
    monkeypatch.setattr(documents, "Store", lambda: workspace)
    app = AppTest.from_file(APP, default_timeout=20)
    app.secrets.update({"STORAGE_BACKEND": "supabase"})
    app.run()
    assert not app.exception and not app.error
    assert "Backup & sharing" in app.radio(key="page").options


def test_offline_network_guard_blocks_dns_and_connections():
    code = "from launcher import enforce_offline_network; import socket; enforce_offline_network(); socket.create_connection(('example.com',443),timeout=1)"
    result = subprocess.run([sys.executable, "-c", code], cwd=APP.parent, capture_output=True, text=True)
    assert result.returncode != 0
    assert "blocks external network" in result.stderr


def test_history_queries_do_not_load_all_payloads(workspace):
    for number in range(70):
        workspace.save_record(f"Run {number}", {"large": "payload" * 100})
    summaries = workspace.record_summaries()
    assert len(summaries) == 50
    assert all("payload" not in row for row in summaries)
    found = workspace.record_summaries("Run 69")
    assert len(found) == 1 and json.loads(workspace.record(found[0]["id"])["payload"])["large"]


def test_pdf_failure_keeps_generated_word_files(workspace, monkeypatch):
    import streamlit as st
    original_editor = st.data_editor
    rows = [{"description": "Sample", "quantity": 2, "unit": "kg", "unit_price": 10}]
    monkeypatch.setattr(st, "data_editor", lambda data, **kwargs: rows if kwargs.get("key") == "quotation_rows" else original_editor(data, **kwargs))
    monkeypatch.setattr(documents, "Store", lambda: workspace)
    monkeypatch.setattr(documents, "pdf_available", lambda: "converter")
    monkeypatch.setattr(documents, "convert_pdfs", lambda *_: (_ for _ in ()).throw(ValueError("Simulated converter failure")))
    app = AppTest.from_file(APP, default_timeout=20).run()
    app.radio(key="page").set_value("Quotations").run()
    app.text_input(key="quotation_number").set_value("TEST-PDF").run()
    app.text_input(key="quote_customer_name").set_value("Sample Customer").run()
    app.checkbox(key="pdf_quotation").check().run()
    app.button(key="generate_quotation").click().run()
    assert not app.exception and app.warning
    output = app.session_state["output_quotation"]
    assert output["files"] and all(name.endswith(".docx") for name in output["files"])
    assert len(workspace.records()) == 1
    assert list((workspace.root / "exports").rglob("*.docx"))


def test_catalogue_draft_survives_navigation(workspace, monkeypatch):
    import streamlit as st
    original_editor = st.data_editor
    entered = {"active": True}
    def table(data, **kwargs):
        if kwargs.get("key", "").startswith("catalog_editor_") and entered["active"]:
            return [data[0] | {"description": "Draft description"}] + data[1:]
        return original_editor(data, **kwargs)
    monkeypatch.setattr(st, "data_editor", table)
    monkeypatch.setattr(documents, "Store", lambda: workspace)
    app = AppTest.from_file(APP, default_timeout=20).run()
    app.radio(key="page").set_value("Tenders & items").run()
    app.selectbox(key="catalog_reference").set_value("SPMC/03/2026").run()
    app.radio(key="page").set_value("Suppliers").run()
    entered["active"] = False
    app.radio(key="page").set_value("Tenders & items").run()
    assert not app.exception
    assert app.session_state["_catalog_editor_draft_SPMC/03/2026"][0]["description"] == "Draft description"


@pytest.mark.skipif(os.name != "nt", reason="Windows desktop lifecycle")
def test_duplicate_launcher_reuses_server_and_rejects_unauthorized_stop(tmp_path):
    from urllib.request import Request, build_opener, ProxyHandler
    from urllib.error import HTTPError
    command = [sys.executable, str(APP.parent / "launcher.py")]
    flags = ["--no-browser", "--data-dir", str(tmp_path)]
    process = subprocess.Popen(command + flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        metadata = tmp_path / "launcher.json"
        deadline = time.monotonic() + 40
        while not metadata.exists():
            assert process.poll() is None, "Launcher exited before readiness"
            assert time.monotonic() < deadline, "Launcher readiness timeout"
            time.sleep(0.1)
        state = json.loads(metadata.read_text())
        second = subprocess.run(command + flags, capture_output=True, text=True, timeout=15)
        assert second.returncode == 0, second.stderr
        assert json.loads(metadata.read_text())["pid"] == state["pid"]
        request = Request(state["control_url"] + "/stop", data=b"", method="POST", headers={"X-USECTA-Token": "wrong-token"})
        with pytest.raises(HTTPError) as failure:
            build_opener(ProxyHandler({})).open(request, timeout=3)
        assert failure.value.code == 403
        assert process.poll() is None
    finally:
        if (tmp_path / "launcher.json").exists():
            subprocess.run(command + ["--stop", "--data-dir", str(tmp_path)], check=True, timeout=10)
        else:
            process.terminate()
        process.wait(timeout=20)
    assert not metadata.exists()
