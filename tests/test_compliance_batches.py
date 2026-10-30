from copy import deepcopy
from decimal import Decimal
import io
import json

from docx import Document
import pytest

from cloud_store import SupabaseStore
from compliance_batches import (SHARED_DEFAULTS, amount_in_words, batch_payload, batch_values,
    item_defaults, item_totals, save_supplier_draft, schedule_for, supplier_draft)
from documents import Store
from statement_compliance import regenerate_statement
from workflows import prepare_workspace
from workspace_archive import export_workspace, restore_workspace


def make_draft(supplier=None, numbers=("6", "12"), reference="SPMC/03/2026"):
    draft = supplier_draft(supplier or {"supplier_name": "Test Supplier"}, reference)
    schedule = schedule_for(reference)
    draft["selected_items"] = list(numbers)
    for number in numbers:
        draft["items"][number] = item_defaults({"item_number": number, "description": "Catalogue product", "quantity_kg": "100"}, schedule.get(number))
        draft["items"][number].update(price_per_kg="9.287", commission="7%")
    return draft


def test_all_fifty_schedule_values_and_exceptions_are_bound_to_this_tender():
    schedule = schedule_for("SPMC/03/2026")
    assert list(schedule) == [str(i) for i in range(1, 51)]
    # Independent transcription of the security column, in thousands of LKR.
    security = [450,20,45,500,250,1400,10,300,150,350,200,4000,50,1200,170,35,500,300,
                90,120,60,950,100,70,25,400,10,10,15,20,15,80,130,60,250,20,600,100,
                20,40,80,15,5,25,25,5,100,5,10,5]
    for number, amount in zip(schedule, security):
        row = schedule[number]
        assert Decimal(row["bid_security_lkr"]) == amount * 1000
        assert row["packaging"] and row["delivery_schedule"] and row["shelf_life_requirement"]
        assert row["source_page"] in range(2, 10)
    assert schedule["12"]["quantity_kg"] == "16000"
    for number in ("12", "35", "37", "38", "41"):
        assert "February 2027" in schedule[number]["delivery_schedule"]
        assert "December 2026" in schedule[number]["delivery_schedule"]
    assert schedule["18"]["required_transport"] == "By Air"
    assert "light & heat" in schedule["42"]["packaging"]
    assert "DOUBLE POLYTHENE" in schedule["14"]["packaging"]
    assert schedule_for("SPMC/02/2026") == {}
    schedule["1"]["packaging"] = "Changed by caller"
    assert schedule_for("SPMC/03/2026")["1"]["packaging"] != "Changed by caller"


@pytest.mark.parametrize("amount,currency,words", [
    ("18574", "USD", "Eighteen Thousand Five Hundred Seventy Four United States Dollars"),
    ("0", "LKR", "Zero Sri Lankan Rupees"),
    ("1.01", "USD", "One United States Dollar and One Cent"),
    ("1234.567", "EUR", "One Thousand Two Hundred Thirty Four Euros and Fifty Seven Cents"),
    ("2.02", "GBP", "Two Pounds Sterling and Two Pence"),
    ("999999999999.99", "USD", "Nine Hundred Ninety Nine Billion Nine Hundred Ninety Nine Million Nine Hundred Ninety Nine Thousand Nine Hundred Ninety Nine United States Dollars and Ninety Nine Cents"),
])
def test_amount_in_words(amount, currency, words):
    assert amount_in_words(amount, currency) == words


def test_batch_defaults_precise_prices_shared_values_and_manual_total_override():
    draft = make_draft()
    draft["shared"].update(manufacturer="Shared Manufacturer", shelf_life="48 months", origin="China")
    draft["items"]["6"].update(transport="Shanghai - By Sea")
    draft["items"]["12"].update(transport="Ningbo - By Sea", total_override="1234.565")
    values = batch_values(draft)
    assert values[0]["total_cost"] == "USD 13,930.50"
    assert values[1]["total_cost"] == "USD 1,234.57"
    assert values[0]["price_per_kg"] == "USD 9.287 / kg"
    assert values[0]["transport"] == "Shanghai - By Sea"
    for value in values:
        assert value["manufacturer"] == "Shared Manufacturer" and value["shelf_life"] == "48 months"
        assert value["payment"] == "L/C at Sight" and value["sample"] == "Yes"
        assert value["offer_response"] == "Yes" and value["coa"] == "Yes - COA Complies"
        assert "Submitted" not in value["security"]
    assert values[0]["security"] == "SL Rs. 1,400,000.00"
    assert values[1]["security"] == "SL Rs. 4,000,000.00"
    draft["items"]["6"]["quantity_kg"] = "100"
    values = batch_values(draft)
    assert values[0]["required_quantity"] == "1,500 kg"
    assert values[0]["offered_quantity"] == "100 kg"
    assert values[0]["total_cost"] == "USD 928.70"


@pytest.mark.parametrize("price", ["-5", "NaN", "Infinity", "invalid", "1e12", "0.0000000000001"])
def test_invalid_prices_are_rejected_for_generation(price):
    draft = make_draft(numbers=("6",))
    draft["items"]["6"]["price_per_kg"] = price
    with pytest.raises(ValueError):
        batch_values(draft)


def test_air_requirement_and_different_tender_never_receive_spmc03_defaults():
    draft = make_draft(numbers=("18",))
    assert batch_values(draft)[0]["transport"] == "By Air"
    draft["items"]["18"]["transport"] = "By Sea"
    with pytest.raises(ValueError, match="requires delivery by air"):
        batch_values(draft)
    other = make_draft(numbers=("18",), reference="OTHER/TENDER")
    row = other["items"]["18"]
    assert row["bid_security_lkr"] == row["packaging"] == row["delivery_schedule"] == ""
    assert row["item_name"] == "Catalogue product" and row["quantity_kg"] == "100"


def test_supplier_drafts_can_be_saved_unfinished_and_survive_backup_and_company_profile_changes(tmp_path):
    store = Store(tmp_path / "original")
    supplier = {"supplier_name": "Test Supplier", "supplier_country": "China", "supplier_registration_number": "123"}
    store.save_supplier(supplier, "one")
    draft = make_draft(supplier)
    draft["items"]["6"]["price_per_kg"] = ""
    draft["shared"]["manufacturer"] = "Manufacturer A"
    save_supplier_draft(store, "one", draft)
    other = make_draft(supplier, reference="OTHER/TENDER")
    save_supplier_draft(store, "one", other)
    stored = store.suppliers()["one"]
    assert stored["supplier_registration_number"] == "123"
    assert len(stored["statement_compliance"]["drafts"]) == 2
    loaded = supplier_draft(stored, "SPMC/03/2026")
    assert loaded["shared"]["manufacturer"] == "Manufacturer A"
    assert loaded["items"]["6"]["price_per_kg"] == ""
    loaded["shared"]["manufacturer"] = "Changed only in memory"
    assert supplier_draft(stored, "SPMC/03/2026")["shared"]["manufacturer"] == "Manufacturer A"
    restored = Store(tmp_path / "restored")
    restore_workspace(restored, export_workspace(store))
    assert restored.suppliers() == store.suppliers()


def test_saved_batch_is_immutable_after_supplier_changes_and_recreates_all_files(tmp_path):
    store = Store(tmp_path)
    prepare_workspace(store)
    draft = make_draft()
    draft["items"]["12"]["price_per_kg"] = "3.25"
    payload = batch_payload(draft, "one", "Supplier / <A>", False)
    original = regenerate_statement(payload)
    assert len(original) == 2 and len(set(original)) == 2
    assert all("/" not in name for name in original)
    docs = [Document(io.BytesIO(content)) for content in original.values()]
    assert "USD 13,930.50" in docs[0].tables[0].rows[9].cells[2].text
    assert "USD 52,000.00" in docs[1].tables[0].rows[9].cells[2].text
    draft["shared"]["origin"] = "New origin"
    draft["items"]["6"]["price_per_kg"] = "1000"
    assert regenerate_statement(payload) == original
    payload["statements"].append(deepcopy(payload["statements"][0]))
    with pytest.raises(ValueError, match="same output filename"):
        regenerate_statement(payload)


def test_drafts_persist_in_supabase_after_all_local_cache_is_lost(tmp_path):
    from test_cloud import FakeServer
    server = FakeServer()
    first = SupabaseStore(server, cache_root=tmp_path / "first")
    first.save_supplier({"supplier_name": "Cloud Supplier"}, "cloud-one")
    draft = make_draft()
    save_supplier_draft(first, "cloud-one", draft)
    second = SupabaseStore(server, cache_root=tmp_path / "empty-cache")
    reopened = supplier_draft(second.suppliers()["cloud-one"], "SPMC/03/2026")
    assert reopened["selected_items"] == ["6", "12"]
    assert reopened["items"]["6"]["price_per_kg"] == "9.287"
