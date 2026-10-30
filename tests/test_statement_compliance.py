import io
import json
import hashlib
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
import pytest
from streamlit.testing.v1 import AppTest

import documents
from documents import Store, template_variables
from statement_compliance import (DEFAULTS, FIELDS, regenerate_statement, statement_files,
                                  statement_payload, template_bytes, validate_statement)
from workflows import prepare_workspace
from workspace_archive import export_workspace, restore_workspace
from compliance_batches import (batch_values, batch_payload, supplier_draft, item_defaults, schedule_for,
                                save_supplier_draft, amount_in_words, item_totals)

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
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                assert cell.vertical_alignment == WD_CELL_VERTICAL_ALIGNMENT.CENTER
                assert all(p.alignment == WD_ALIGN_PARAGRAPH.CENTER for p in cell.paragraphs)


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
    store.save_supplier({"supplier_name": "Supplier One", "supplier_address": "Address One", "supplier_country": "China"}, "one")
    store.save_supplier({"supplier_name": "Supplier Two", "supplier_address": "Address Two"}, "two")
    return store


def application():
    app = AppTest.from_file(ROOT / "app.py", default_timeout=25).run()
    app.radio(key="page").set_value("Statement of Compliance").run()
    return app.selectbox(key="compliance_supplier").set_value("one").run()


def select_items(app, numbers):
    app.multiselect[0].set_value(numbers).run()
    assert not app.exception


def field(app, suffix, kind="text_input"):
    return next(w for w in getattr(app, kind) if w.key and w.key.endswith("_" + suffix))


def edit_prices(app, changes):
    grids = app.session_state["_compliance_grid"]
    context = hashlib.sha256((app.selectbox(key="compliance_supplier").value + "\n" + app.selectbox(key="compliance_reference").value).encode()).hexdigest()[:16]
    editor_key = grids[context]["key"]
    app.session_state[editor_key] = {"edited_rows": changes, "added_rows": [], "deleted_rows": []}
    app.run()
    assert not app.exception


def test_batch_save_reopen_generation_stale_downloads_and_history(workspace):
    app = application()
    assert not app.exception
    assert app.button(key="soc_generate").disabled
    assert field(app, "coa").value == "Yes - COA Complies"
    select_items(app, ["6", "12"])
    field(app, "manufacturer", "text_area").set_value("Shared Manufacturer\nFactory Address").run()
    edit_prices(app, {0: {"price_per_kg": "9.287", "commission": "7%", "transport": "Shanghai - By Sea"},
                      1: {"price_per_kg": "2.50", "commission": "5%", "transport": "Ningbo - By Sea"}})
    app.button(key="soc_save").click().run()
    assert not app.exception and not app.error
    assert workspace.records() == [], "Saving an unfinished draft must not generate documents"
    saved = workspace.suppliers()["one"]["statement_compliance"]["drafts"]["SPMC/03/2026"]
    assert saved["items"]["6"]["price_per_kg"] == "9.287"
    restarted = application()
    assert restarted.multiselect[0].value == ["6", "12"]
    assert field(restarted, "manufacturer", "text_area").value == "Shared Manufacturer\nFactory Address"
    app = restarted
    app.button(key="soc_generate").click().run()
    assert not app.exception and not app.error
    original = app.session_state["_compliance_output"]["files"]
    assert len(original) == 2
    with zipfile.ZipFile(io.BytesIO(app.session_state["_compliance_output"]["zip"])) as archive:
        assert set(archive.namelist()) == set(original)
    record = workspace.records()[0]
    payload = json.loads(record["payload"])
    assert payload["workflow"] == "statement_compliance"
    assert payload["statements"][0]["total_cost"] == "USD 13,930.50"
    assert payload["statements"][1]["total_cost"] == "USD 40,000.00"
    assert len(list((workspace.root / "exports").rglob("*.docx"))) == 2
    app.radio(key="page").set_value("Suppliers").run()
    app.radio(key="page").set_value("Statement of Compliance").run()
    assert not app.exception
    assert app.multiselect[0].value == ["6", "12"]
    field(app, "origin").set_value("New origin").run()
    assert not any("statements generated" in e.value for e in app.success)
    app.selectbox(key="history").set_value(record["id"]).run()
    next(b for b in app.button if b.label == "Regenerate saved run").click().run()
    assert not app.exception and not app.error
    assert app.session_state["history_output"]["files"] == original
    app.button(key="history_edit_compliance").click().run()
    assert not app.exception
    assert field(app, "origin").value == "China"


def test_suppliers_stay_separate_selection_changes_and_navigation_preserve_unsaved_edits(workspace):
    before = workspace.catalog("SPMC/03/2026")
    app = application()
    select_items(app, ["15"])
    edit_prices(app, {0: {"price_per_kg": "4.567", "commission": "7%"}})
    field(app, "manufacturer", "text_area").set_value("Manufacturer One").run()
    select_items(app, ["15", "18"])
    select_items(app, ["18"])
    select_items(app, ["15", "18"])
    app.selectbox(key="compliance_supplier").set_value("two").run()
    select_items(app, ["12"])
    field(app, "manufacturer", "text_area").set_value("Manufacturer Two").run()
    app.button(key="soc_save").click().run()
    app.selectbox(key="compliance_supplier").set_value("one").run()
    assert not app.exception
    assert app.multiselect[0].value == ["15", "18"]
    assert field(app, "manufacturer", "text_area").value == "Manufacturer One"
    app.button(key="soc_save").click().run()
    assert not app.exception
    saved = workspace.suppliers()["one"]["statement_compliance"]["drafts"]["SPMC/03/2026"]
    assert saved["items"]["15"]["price_per_kg"] == "4.567"
    assert saved["items"]["18"]["transport"] == "By Air"
    assert saved["items"]["15"]["bid_security_lkr"] == "170000.00"
    assert workspace.catalog("SPMC/03/2026") == before
    assert workspace.suppliers()["two"]["supplier_address"] == "Address Two"


def test_pdf_failure_keeps_word_and_saved_record(workspace, monkeypatch):
    monkeypatch.setattr(documents, "pdf_available", lambda: "converter")
    monkeypatch.setattr(documents, "convert_pdfs", lambda *_: (_ for _ in ()).throw(ValueError("Converter failed")))
    app = application()
    select_items(app, ["6", "12"])
    edit_prices(app, {0: {"price_per_kg": "3"}, 1: {"price_per_kg": "4"}})
    app.button(key="soc_generate").click().run()
    assert not app.exception and not app.error
    assert all(name.endswith(".docx") for name in app.session_state["_compliance_output"]["files"])
    assert any("Word documents were saved" in w.value for w in app.warning)
    assert json.loads(workspace.records()[0]["payload"])["with_pdf"]


def test_successful_pdf_is_downloadable_in_cloud_without_local_exports(workspace, monkeypatch):
    import cloud_access
    monkeypatch.setattr(cloud_access, "workspace_store", lambda: (workspace, True))
    monkeypatch.setattr(documents, "pdf_available", lambda: "converter")
    monkeypatch.setattr(documents, "convert_pdfs", lambda files: {name.replace(".docx", ".pdf"): b"%PDF-test" for name in files})
    app = application()
    select_items(app, ["6", "12"])
    edit_prices(app, {0: {"price_per_kg": "3"}, 1: {"price_per_kg": "4"}})
    app.button(key="soc_generate").click().run()
    assert not app.exception and not app.error
    files = app.session_state["_compliance_output"]["files"]
    assert len(files) == 4 and any(name.endswith(".pdf") for name in files)
    assert not (workspace.root / "exports").exists()
    payload = json.loads(workspace.records()[0]["payload"])
    assert "output_directory" not in payload


def test_unfinished_work_saves_without_prices_and_supplier_editor_preserves_it(workspace):
    app = application()
    select_items(app, ["6", "12"])
    assert app.button(key="soc_generate").disabled
    field(app, "manufacturer", "text_area").set_value("Unfinished Manufacturer").run()
    app.button(key="soc_save_top").click().run()
    assert not app.exception and not app.error
    assert workspace.records() == []
    app.radio(key="page").set_value("Suppliers").run()
    app.selectbox(key="edit_supplier").set_value("one").run()
    app.text_input(key="supplier_one_supplier_country").set_value("Updated country")
    next(b for b in app.button if b.label == "Save supplier").click().run()
    assert not app.exception and not app.error
    assert "statement_compliance" in workspace.suppliers()["one"]
    restarted = application()
    assert restarted.multiselect[0].value == ["6", "12"]
    assert field(restarted, "manufacturer", "text_area").value == "Unfinished Manufacturer"
    assert restarted.button(key="soc_generate").disabled


def test_add_supplier_inline_starts_an_independent_draft(workspace):
    app = application()
    app.text_input(key="soc_new_supplier_name").set_value("Inline Supplier")
    next(b for b in app.button if b.label == "Create supplier").click().run()
    assert not app.exception and not app.error
    new_id = app.selectbox(key="compliance_supplier").value
    assert workspace.suppliers()[new_id]["supplier_name"] == "Inline Supplier"
    assert app.multiselect[0].value == []
