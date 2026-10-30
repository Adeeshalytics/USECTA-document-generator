import io
import json
from pathlib import Path

from docx import Document
import pytest
from streamlit.testing.v1 import AppTest

import documents
from documents import Store, template_variables
from statement_compliance import (DEFAULTS, FIELDS, regenerate_statement, statement_files,
                                  statement_payload, template_bytes, validate_statement)
from workflows import prepare_workspace
from workspace_archive import export_workspace, restore_workspace

ROOT = Path(__file__).resolve().parents[1]


def sample_values():
    return DEFAULTS | {"item_number": "17", "item_name": "Sample acid BP 2025",
        "offered_item": "Sample acid BP 2025 <A> & B", "offered_quantity": "2,000 kg",
        "required_quantity": "2,000 kg", "price_per_kg": "USD 9.287 / kg",
        "total_cost": "USD 18,574", "manufacturer": "Example Manufacturer\nFactory address",
        "manufacturer_phone": "+86 12345", "manufacturer_email": "factory@example.test"}


def test_template_contains_complete_two_page_form_and_preserves_entered_values():
    values = sample_values()
    assert template_variables(template_bytes()) == (set(FIELDS) - {"item_number"}) | {"supply_item", "offer_valid_until", "security_valid_until"}
    content = next(iter(statement_files(values).values()))
    doc = Document(io.BytesIO(content))
    text = "\n".join(p.text for p in doc.paragraphs) + "\n" + "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
    assert "SUPPLY OF ITEM No. 17 - Sample acid BP 2025" in text
    assert "Sample acid BP 2025 <A> & B" in text
    assert "01.02.2027" in text and "01.03.2027" in text
    assert "91 days" in text and "119 days" in text
    assert "USD 9.287 / kg" in text and "USD 18,574" in text
    assert "{{" not in text and "{%" not in text
    assert len(doc.tables) == 2
    numbers = [r.cells[0].text for t in doc.tables for r in t.rows if r.cells[0].text]
    assert numbers == [f"{i}." for i in range(1, 21)]
    assert doc.tables[-1].rows[-1].cells[-1].text == ""
    assert all(r.height_rule != 2 for t in doc.tables for r in t.rows)


@pytest.mark.parametrize("overrides,match", [({"item_name": " "}, "required item"),
    ({"offer_valid_until": "2027-02-30"}, "Offer validity"),
    ({"security_valid_until": ""}, "Bid security"), ({"coa": "bad\x00value"}, "control"),
    ({"packaging": "x" * 3001}, "3,000"), ({"origin": 5}, "enter text")])
def test_invalid_statement_data(overrides, match):
    with pytest.raises(ValueError, match=match):
        validate_statement(sample_values() | overrides)


def test_saved_snapshot_survives_template_and_catalogue_changes_and_backup(tmp_path, monkeypatch):
    store = Store(tmp_path / "original")
    prepare_workspace(store)
    payload = statement_payload(sample_values(), False)
    original = regenerate_statement(payload)
    store.save_record("Statement", payload)
    monkeypatch.setattr("statement_compliance.template_bytes", lambda: b"new template")
    assert regenerate_statement(payload) == original
    restored = Store(tmp_path / "restored")
    restore_workspace(restored, export_workspace(store))
    assert regenerate_statement(json.loads(restored.records()[0]["payload"])) == original
    with pytest.raises(ValueError, match="missing or invalid"):
        regenerate_statement(payload | {"template_base64": "!invalid"})


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    store = Store(tmp_path)
    prepare_workspace(store)
    monkeypatch.setattr(documents, "Store", lambda: store)
    monkeypatch.setattr(documents, "pdf_available", lambda: None)
    return store


def application():
    app = AppTest.from_file(ROOT / "app.py", default_timeout=25).run()
    return app.radio(key="page").set_value("Statement of Compliance").run()


def test_manual_generation_navigation_stale_downloads_and_history(workspace):
    app = application()
    assert not app.exception
    assert app.button(key="compliance_generate").disabled
    assert app.text_area(key="compliance_coa").value == ""
    app.text_area(key="compliance_item_name").set_value("Manual product & specification").run()
    app.text_area(key="compliance_offered_item").set_value("Offered product").run()
    app.button(key="compliance_generate").click().run()
    assert not app.exception and not app.error
    original = app.session_state["compliance_output"]["files"]
    record = workspace.records()[0]
    payload = json.loads(record["payload"])
    assert payload["workflow"] == "statement_compliance"
    assert payload["values"]["item_name"] == "Manual product & specification"
    assert list((workspace.root / "exports").rglob("*.docx"))
    app.radio(key="page").set_value("Suppliers").run()
    app.radio(key="page").set_value("Statement of Compliance").run()
    assert not app.exception
    assert app.text_area(key="compliance_item_name").value == "Manual product & specification"
    app.text_area(key="compliance_offered_item").set_value("Changed offer").run()
    assert not any("Statement generated" in e.value for e in app.success)
    app.selectbox(key="history").set_value(record["id"]).run()
    next(b for b in app.button if b.label == "Regenerate saved run").click().run()
    assert not app.exception and not app.error
    assert app.session_state["history_output"]["files"] == original


def test_catalogue_and_supplier_loading_never_modify_source_profiles(workspace):
    before = workspace.catalog("SPMC/03/2026")
    sid = workspace.save_supplier({"supplier_name": "Foreign Bidder", "supplier_address": "Bidder address"})
    app = application()
    app.selectbox(key="compliance_reference").set_value("SPMC/03/2026").run()
    app.selectbox(key="compliance_catalogue_SPMC/03/2026").set_value("15").run()
    app.button(key="compliance_load_item").click().run()
    assert not app.exception
    item = next(row for row in before if row["item_number"] == "15")
    assert app.text_area(key="compliance_item_name").value == item["description"]
    assert app.text_area(key="compliance_offered_item").value == item["description"]
    assert app.text_input(key="compliance_offered_quantity").value == item["quantity_kg"] + " kg"
    app.selectbox(key="compliance_supplier").set_value(sid).run()
    app.button(key="compliance_load_bidder").click().run()
    assert not app.exception
    assert app.text_area(key="compliance_bidder").value == "Foreign Bidder\nBidder address"
    assert app.text_area(key="compliance_manufacturer").value == ""
    assert workspace.catalog("SPMC/03/2026") == before
    assert workspace.suppliers()[sid]["supplier_address"] == "Bidder address"


def test_pdf_failure_keeps_word_and_saved_record(workspace, monkeypatch):
    monkeypatch.setattr(documents, "pdf_available", lambda: "converter")
    monkeypatch.setattr(documents, "convert_pdfs", lambda *_: (_ for _ in ()).throw(ValueError("Converter failed")))
    app = application()
    app.text_area(key="compliance_item_name").set_value("Test item").run()
    app.button(key="compliance_generate").click().run()
    assert not app.exception and not app.error
    assert all(name.endswith(".docx") for name in app.session_state["compliance_output"]["files"])
    assert any("Word document was saved" in w.value for w in app.warning)
    assert json.loads(workspace.records()[0]["payload"])["with_pdf"]


def test_successful_pdf_is_downloadable_in_cloud_without_local_exports(workspace, monkeypatch):
    import cloud_access
    monkeypatch.setattr(cloud_access, "workspace_store", lambda: (workspace, True))
    monkeypatch.setattr(documents, "pdf_available", lambda: "converter")
    monkeypatch.setattr(documents, "convert_pdfs", lambda files: {next(iter(files)).replace(".docx", ".pdf"): b"%PDF-test"})
    app = application()
    app.text_area(key="compliance_item_name").set_value("Cloud item").run()
    app.button(key="compliance_generate").click().run()
    assert not app.exception and not app.error
    files = app.session_state["compliance_output"]["files"]
    assert len(files) == 2 and any(name.endswith(".pdf") for name in files)
    assert not (workspace.root / "exports").exists()
    payload = json.loads(workspace.records()[0]["payload"])
    assert "output_directory" not in payload
