"""Regression tests for the reported date/supplier/item problems and app icon."""
from datetime import date
from pathlib import Path

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

import documents
from documents import Store
from workflows import prepare_workspace, tender_context, tender_jobs

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = "SPMC/03/2026"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    store = Store(tmp_path)
    prepare_workspace(store)
    monkeypatch.setattr(documents, "Store", lambda: store)
    return store


def application():
    return AppTest.from_file(ROOT / "app.py", default_timeout=20).run()


def tender_editor(app):
    app.radio(key="page").set_value("Tenders & items").run()
    app.selectbox(key="edit_tender").set_value(REFERENCE).run()
    return app.date_input(key=f"catalog_validity_date_{REFERENCE}")


def save_tender(app):
    next(button for button in app.button if button.label == "Save tender").click().run()
    assert not app.exception


def test_entered_validity_is_saved_without_enable_checkbox_and_survives_restart(workspace):
    app = application()
    validity = tender_editor(app)
    assert validity.value is None
    assert not any("Specify bid acceptance" in widget.label for widget in app.checkbox)
    validity.set_value(date(2027, 2, 3))
    save_tender(app)
    assert workspace.tenders()[REFERENCE]["bid_valid_until"] == "2027-02-03"
    assert any("2027-02-03" in success.value for success in app.success)
    restarted = application()
    assert tender_editor(restarted).value == date(2027, 2, 3)


def test_blank_validity_is_not_assumed_from_closing_date(workspace):
    app = application()
    tender_editor(app)
    save_tender(app)
    assert workspace.tenders()[REFERENCE]["bid_valid_until"] == ""
    assert any("No bid acceptance validity date was saved" in info.value for info in app.info)


def test_invalid_validity_does_not_overwrite_saved_tender(workspace):
    before = workspace.tenders()[REFERENCE]
    app = application()
    tender_editor(app).set_value(date(2026, 1, 1))
    save_tender(app)
    assert app.error
    assert workspace.tenders()[REFERENCE] == before


def test_saved_validity_can_be_explicitly_cleared(workspace):
    workspace.save_tender(REFERENCE, workspace.tenders()[REFERENCE] | {"bid_valid_until": "2027-02-03"})
    app = application()
    tender_editor(app).set_value(None)
    save_tender(app)
    assert workspace.tenders()[REFERENCE]["bid_valid_until"] == ""


def test_all_missing_tender_requirements_are_reported_without_placeholder_ids(workspace):
    templates = [template for template in workspace.templates() if template["workflow"] == "tender"]
    data = tender_context(REFERENCE, workspace.tenders()[REFERENCE], [], {}, date.today(), date.today())
    with pytest.raises(ValueError) as error:
        tender_jobs(workspace, [template["id"] for template in templates], data)
    message = str(error.value)
    assert "Bid Form" in message and "Agency Agreement" in message
    assert "bid acceptance validity date" in message
    assert "Registration number in Suppliers" in message
    assert "Select at least one item" in message
    assert "agreement_item_names" not in message
    assert "supplier_registration_number" not in message
    assert "bid_valid_until" not in message


def test_fixing_requirements_enables_real_generation_and_navigation_preserves_selection(workspace):
    supplier = workspace.save_supplier({"supplier_name": "Test Supplier", "supplier_country": "China",
        "supplier_address": "Test Address", "supplier_registration_number": "TEST-123"})
    app = application()
    app.selectbox(key="tender_reference").set_value(REFERENCE).run()
    ids = [template["id"] for template in workspace.templates() if template["workflow"] == "tender"]
    app.multiselect(key="tender_templates").set_value(ids).run()
    assert app.button(key="generate_tender").disabled
    assert len(app.warning) == 1, "One consolidated message, not duplicate date warnings"
    app.multiselect(key=f"selected_items_{REFERENCE}").set_value(["2"]).run()
    app.selectbox(key="tender_supplier").set_value(supplier).run()
    app.button(key="edit_tender_dates").click().run()
    assert app.radio(key="page").value == "Tenders & items"
    assert app.selectbox(key="edit_tender").value == REFERENCE
    app.date_input(key=f"catalog_validity_date_{REFERENCE}").set_value(date(2027, 2, 3))
    save_tender(app)
    app.radio(key="page").set_value("Tender documents").run()
    assert app.multiselect(key=f"selected_items_{REFERENCE}").value == ["2"]
    assert app.selectbox(key="tender_supplier").value == supplier
    assert not app.warning and not app.button(key="generate_tender").disabled
    app.button(key="edit_selected_supplier").click().run()
    assert app.radio(key="page").value == "Suppliers"
    assert app.selectbox(key="edit_supplier").value == supplier
    app.radio(key="page").set_value("Tender documents").run()
    app.button(key="generate_tender").click().run()
    assert not app.exception and not app.error
    assert len(app.session_state["output_tender"]["files"]) == 6
    assert len(workspace.records()) == 1


def test_envelopes_do_not_require_unknown_validity_or_supplier(workspace):
    app = application()
    app.selectbox(key="tender_reference").set_value(REFERENCE).run()
    envelope = next(template for template in workspace.templates() if template["name"] == "Envelop covers")
    app.multiselect(key="tender_templates").set_value([envelope["id"]]).run()
    assert not app.warning and not app.button(key="generate_tender").disabled
    app.button(key="generate_tender").click().run()
    assert not app.exception and len(app.session_state["output_tender"]["files"]) == 1


def test_icon_has_all_windows_sizes_and_packaging_uses_supplied_artwork():
    with Image.open(ROOT / "assets/usecta-icon.ico") as icon:
        assert icon.ico.sizes() == {(size, size) for size in (16, 24, 32, 48, 64, 128, 256)}
        assert icon.mode == "RGBA"
    assert "assets" in (ROOT / "USECTA.spec").read_text()
    assert "MUI_UNICON" in (ROOT / "installer/USECTA.nsi").read_text()
