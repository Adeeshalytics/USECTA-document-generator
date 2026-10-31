import io
import json
from pathlib import Path

from docx import Document
import pytest
from streamlit.testing.v1 import AppTest

import documents
from compliance_batches import item_defaults, save_supplier_draft, schedule_for, supplier_draft
from documents import Store
from sample_submission import (clean_draft, letter_context, letter_payload, load_draft,
                               new_draft, regenerate_letter, save_draft)
from workflows import prepare_workspace
from workspace_archive import export_workspace, restore_workspace

ROOT = Path(__file__).resolve().parents[1]


def sample_draft(count=3):
    draft = new_draft("SPMC/03/2026")
    draft["document_date"] = "2026-10-31"
    for i in range(1, count + 1):
        number = str(i)
        draft["selected_items"].append(number)
        draft["items"][number] = {"item_number": number, "description": f"Sample <{i}> & specification"}
    return draft


def text_of(content):
    doc = Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs)


def test_multi_item_letter_dynamic_quantity_date_enclosure_and_xml_escaping():
    payload = letter_payload(sample_draft(), None, "", False)
    files = regenerate_letter(payload)
    assert len(files) == 1
    text = text_of(next(iter(files.values())))
    assert "31/10/2026" in text
    assert text.count("SPMC/03/2026") == 2 and "SPMC/02/2026" not in text
    assert "3.   Sample <3> & specification - No. 3" in text
    assert "Two sample packs per item for the 3 selected items" in text
    assert "Original Certificate of Analysis" in text
    assert "evaluation purposes only" in text
    assert "{{" not in text and "{%" not in text
    assert "Agency Agreement" not in text


def test_single_item_singular_wording_and_coa_can_be_excluded():
    draft = sample_draft(1)
    draft.update(packs_per_item=1, coa_enclosed=False, quantity_note="")
    context = letter_context(draft)
    assert context["tender_item_word"] == "item"
    assert context["quantity_sentence"] == "One sample pack per item for the 1 selected item."
    text = text_of(next(iter(regenerate_letter(letter_payload(draft, None, "", False)).values())))
    assert "Original Certificate of Analysis" not in text
    assert "No. 1" in text


@pytest.mark.parametrize("changes", [{"packs_per_item": 0}, {"packs_per_item": True},
    {"packs_per_item": 101}, {"document_date": "invalid"}, {"selected_items": []},
    {"signatory_name": ""}, {"recipient_name": "bad\x00value"}])
def test_generation_validation(changes):
    with pytest.raises(ValueError):
        letter_context(sample_draft() | changes)


def test_general_drafts_save_unfinished_and_survive_backup(tmp_path):
    store = Store(tmp_path / "source")
    prepare_workspace(store)
    draft = new_draft("SPMC/03/2026")
    draft["document_date"] = "None"
    save_draft(store, None, draft)
    restored = Store(tmp_path / "restored")
    restore_workspace(restored, export_workspace(store))
    assert load_draft(restored, None, "SPMC/03/2026") == draft


def test_snapshot_regeneration_survives_catalogue_template_and_draft_changes(tmp_path, monkeypatch):
    draft = sample_draft(50)
    payload = letter_payload(draft, "one", "Supplier / One", False)
    original = regenerate_letter(payload)
    draft["items"]["1"]["description"] = "Changed afterwards"
    monkeypatch.setattr("sample_submission.template_bytes", lambda: b"changed template")
    assert regenerate_letter(payload) == original
    text = text_of(next(iter(original.values())))
    assert "50.   Sample <50> & specification - No. 50" in text
    with pytest.raises(ValueError, match="missing or invalid"):
        regenerate_letter(payload | {"template_base64": "!invalid"})


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    store = Store(tmp_path)
    prepare_workspace(store)
    store.save_supplier({"supplier_name": "Supplier One"}, "one")
    store.save_supplier({"supplier_name": "Supplier Two"}, "two")
    draft = supplier_draft(store.suppliers()["one"], "SPMC/03/2026")
    schedule = schedule_for("SPMC/03/2026")
    catalog = {row["item_number"]: row for row in store.catalog("SPMC/03/2026")}
    for number in ["6", "12"]:
        draft["items"][number] = item_defaults(catalog[number], schedule[number])
    draft["items"]["6"]["offered_item"] = "Offered sample specification\nsecond line"
    draft["selected_items"] = ["6", "12"]
    save_supplier_draft(store, "one", draft)
    monkeypatch.setattr(documents, "Store", lambda: store)
    monkeypatch.setattr(documents, "pdf_available", lambda: None)
    return store


def application(supplier="one"):
    app = AppTest.from_file(ROOT / "app.py", default_timeout=25).run()
    app.radio(key="page").set_value("Sample submission").run()
    if supplier:
        app.selectbox(key="sample_submission_supplier").set_value(supplier).run()
    assert not app.exception
    return app


def widget(app, suffix, kind="text_input"):
    return next(w for w in getattr(app, kind) if w.key and w.key.endswith("_" + suffix))


def test_supplier_items_autoload_save_restart_navigation_and_history(workspace):
    app = application()
    assert app.multiselect[0].value == ["6", "12"]
    widget(app, "packs_per_item", "number_input").set_value(3).run()
    widget(app, "quantity_note").set_value("sealed sample packs").run()
    app.button(key="sample_letter_save").click().run()
    assert not app.exception and not app.error
    assert workspace.records() == []
    assert "statement_compliance" in workspace.suppliers()["one"]
    app = application()
    assert widget(app, "packs_per_item", "number_input").value == 3
    app.radio(key="page").set_value("Suppliers").run()
    app.radio(key="page").set_value("Sample submission").run()
    assert widget(app, "quantity_note").value == "sealed sample packs"
    app.button(key="sample_letter_generate").click().run()
    assert not app.exception and not app.error
    original = app.session_state["_sample_submission_output"]["files"]
    text = text_of(next(iter(original.values())))
    assert "Offered sample specification second line" in text
    assert "3 sample packs" not in text and "Three sample packs" in text
    assert len(list((workspace.root / "exports").rglob("*.docx"))) == 1
    record = workspace.records()[0]
    widget(app, "quantity_note").set_value("Changed").run()
    assert not any("cover letter generated" in e.value for e in app.success)
    app.selectbox(key="history").set_value(record["id"]).run()
    next(b for b in app.button if b.label == "Regenerate saved run").click().run()
    assert not app.exception
    assert app.session_state["history_output"]["files"] == original
    app.button(key="history_edit_sample_letter").click().run()
    assert not app.exception
    assert widget(app, "quantity_note").value == "sealed sample packs"


def test_prepare_directly_from_compliance_and_supplier_isolation(workspace):
    app = AppTest.from_file(ROOT / "app.py", default_timeout=25).run()
    app.radio(key="page").set_value("Statement of Compliance").run()
    app.selectbox(key="compliance_supplier").set_value("one").run()
    app.button(key="soc_sample_letter").click().run()
    assert not app.exception
    assert app.radio(key="page").value == "Sample submission"
    assert app.multiselect[0].value == ["6", "12"]
    widget(app, "quantity_note").set_value("Supplier one note").run()
    app.selectbox(key="sample_submission_supplier").set_value("two").run()
    assert app.multiselect[0].value == []
    app.multiselect[0].set_value(["15"]).run()
    widget(app, "quantity_note").set_value("Supplier two note").run()
    app.button(key="sample_letter_save").click().run()
    app.selectbox(key="sample_submission_supplier").set_value("one").run()
    assert widget(app, "quantity_note").value == "Supplier one note"
    assert app.multiselect[0].value == ["6", "12"]


def test_edited_sample_description_survives_selection_navigation_and_restart(workspace):
    app = application()
    grids = app.session_state["_sample_submission_grids"]
    editor_key = next(iter(grids.values()))["key"]
    app.session_state[editor_key] = {"edited_rows": {0: {"description": "Exact sample <A> & BP specification"}},
                                     "added_rows": [], "deleted_rows": []}
    app.run()
    app.multiselect[0].set_value(["6", "12", "18"]).run()
    app.radio(key="page").set_value("Suppliers").run()
    app.radio(key="page").set_value("Sample submission").run()
    app.button(key="sample_letter_save").click().run()
    assert not app.exception and not app.error
    saved = load_draft(workspace, "one", "SPMC/03/2026")
    assert saved["items"]["6"]["description"] == "Exact sample <A> & BP specification"
    assert saved["selected_items"] == ["6", "12", "18"]
    restarted = application()
    assert restarted.multiselect[0].value == ["6", "12", "18"]
    restarted.button(key="sample_letter_generate").click().run()
    assert not restarted.exception and not restarted.error
    text = text_of(next(iter(restarted.session_state["_sample_submission_output"]["files"].values())))
    assert "Exact sample <A> & BP specification" in text
    assert "Offered sample" not in text


def test_pdf_failure_keeps_word_and_cloud_writes_no_local_exports(workspace, monkeypatch):
    import cloud_access
    monkeypatch.setattr(cloud_access, "workspace_store", lambda: (workspace, True))
    monkeypatch.setattr(documents, "pdf_available", lambda: "converter")
    monkeypatch.setattr(documents, "convert_pdfs", lambda *_: (_ for _ in ()).throw(ValueError("Converter failed")))
    app = application()
    app.button(key="sample_letter_generate").click().run()
    assert not app.exception and not app.error
    assert any("Word letter was saved" in e.value for e in app.warning)
    assert all(name.endswith(".docx") for name in app.session_state["_sample_submission_output"]["files"])
    assert not (workspace.root / "exports").exists()
    assert "output_directory" not in json.loads(workspace.records()[0]["payload"])


def test_cloud_draft_survives_an_empty_local_cache(tmp_path):
    from cloud_store import SupabaseStore
    from test_cloud import FakeServer
    server = FakeServer()
    first = SupabaseStore(server, cache_root=tmp_path / "one")
    first.save_supplier({"supplier_name": "Cloud supplier"}, "one")
    draft = sample_draft()
    save_draft(first, "one", draft)
    save_draft(first, None, draft)
    second = SupabaseStore(server, cache_root=tmp_path / "new-empty-cache")
    assert load_draft(second, "one", "SPMC/03/2026") == draft
    assert load_draft(second, None, "SPMC/03/2026") == draft
