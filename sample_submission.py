"""Sample submission cover letters, saved drafts and immutable regeneration."""
import base64
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import re

from desktop_paths import asset_root
from documents import filename, render_document

TEMPLATE_NAME = "Sample submission cover letter.docx"
TEXT_DEFAULTS = {
    "recipient_name": "Chairman - Procurement Committee",
    "recipient_address": "State Pharmaceuticals Manufacturing Corporation\nNo.11, Sir John Kotelawala Mawatha, Kandawala\nEstate, Ratmalana, Sri Lanka.",
    "salutation": "Dear Sir/ Madam,",
    "quantity_note": "from the same batch, sufficient for analysis",
    "signatory_name": "Adeesa M.G.P",
    "signatory_designation": "Director - USECTA (Pvt) Ltd",
}


def template_bytes():
    return (asset_root() / "assets" / TEMPLATE_NAME).read_bytes()


def new_draft(reference):
    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    return {"version": 1, "reference": reference, "document_date": today.isoformat(),
            **TEXT_DEFAULTS, "packs_per_item": 2, "coa_enclosed": True,
            "selected_items": [], "items": {}}


def load_draft(store, supplier_id, reference):
    if supplier_id:
        supplier = store.suppliers()[supplier_id]
        saved = supplier.get("sample_submission", {}).get("drafts", {}).get(reference)
    else:
        supplier = {}
        saved = store.profiles().get("sample_submission:" + reference)
    if saved:
        return deepcopy(saved)
    draft = new_draft(reference)
    # Reuse the supplier's selected compliance items without requiring prices.
    compliance = supplier.get("statement_compliance", {}).get("drafts", {}).get(reference, {})
    for number in compliance.get("selected_items", []):
        row = compliance["items"][number]
        draft["selected_items"].append(number)
        draft["items"][number] = {"item_number": number, "description": " ".join((row.get("offered_item") or row["item_name"]).split())}
    return draft


def clean_draft(draft, complete=False):
    if not isinstance(draft, dict) or draft.get("version") != 1:
        raise ValueError("The saved sample submission draft is invalid.")
    result = deepcopy(draft)
    for key in ("reference", "document_date", *TEXT_DEFAULTS):
        value = result.get(key, "")
        if not isinstance(value, str) or len(value) > 3000 or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", value):
            raise ValueError("Use plain text of up to 3,000 characters in each letter field.")
        result[key] = value.strip()
    if not result["reference"]:
        raise ValueError("Choose a tender reference.")
    if not isinstance(result.get("packs_per_item"), int) or isinstance(result["packs_per_item"], bool) or not 1 <= result["packs_per_item"] <= 100:
        raise ValueError("Enter 1 to 100 sample packs per item.")
    if not isinstance(result.get("coa_enclosed"), bool):
        raise ValueError("Choose whether the original Certificate of Analysis is enclosed.")
    selected, items = result.get("selected_items"), result.get("items")
    if not isinstance(selected, list) or any(not isinstance(n, str) for n in selected) or len(selected) > 100 or len(set(selected)) != len(selected) or not isinstance(items, dict):
        raise ValueError("Select up to 100 distinct items.")
    for number, row in items.items():
        if not isinstance(number, str) or not isinstance(row, dict) or row.get("item_number") != number:
            raise ValueError("An item number in the saved letter is invalid.")
        for key in ("item_number", "description"):
            value = row.get(key)
            if not isinstance(value, str) or len(value) > 3000 or re.search(r"[\x00-\x1f\x7f]", value):
                raise ValueError("Use one line of plain text for each item number and description.")
            row[key] = value.strip()
    if any(number not in items for number in selected):
        raise ValueError("A selected item's description is missing.")
    if complete:
        if not selected:
            raise ValueError("Select at least one item for sample submission.")
        if any(not items[n]["description"] for n in selected):
            raise ValueError("Enter the sample description for every selected item.")
        for key, label in [("recipient_name", "Recipient"), ("recipient_address", "Recipient address"),
                           ("salutation", "Salutation"), ("signatory_name", "Signatory name"),
                           ("signatory_designation", "Signatory designation")]:
            if not result[key]:
                raise ValueError("Enter " + label.lower() + ". You can save unfinished changes first.")
        try:
            date.fromisoformat(result["document_date"])
        except ValueError as exc:
            raise ValueError("Enter a valid letter date. You can save unfinished changes first.") from exc
    return result


def save_draft(store, supplier_id, draft):
    cleaned = clean_draft(draft)
    if supplier_id:
        supplier = store.suppliers().get(supplier_id)
        if supplier is None:
            raise ValueError("The selected supplier is no longer available.")
        settings = deepcopy(supplier.get("sample_submission", {}))
        settings.setdefault("drafts", {})[cleaned["reference"]] = cleaned
        store.save_supplier(supplier | {"sample_submission": settings}, supplier_id)
    else:
        store.save_profile("sample_submission:" + cleaned["reference"], cleaned)
    return cleaned


def draft_signature(draft):
    return hashlib.sha256(json.dumps(draft, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def letter_context(draft):
    draft = clean_draft(draft, complete=True)
    count, packs = len(draft["selected_items"]), draft["packs_per_item"]
    pack_word = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five"}.get(packs, str(packs))
    note = " (" + draft["quantity_note"] + ")" if draft["quantity_note"] else ""
    return draft | {"bid_reference": draft["reference"],
        "document_date": date.fromisoformat(draft["document_date"]).strftime("%d/%m/%Y"),
        "sample_items": [draft["items"][n] for n in draft["selected_items"]],
        "tender_item_word": "item" if count == 1 else "items",
        "quantity_sentence": f"{pack_word} sample {'pack' if packs == 1 else 'packs'} per item for the {count} selected {'item' if count == 1 else 'items'}{note}.",
        "coa_paragraph": "The Original Certificate of Analysis for the submitted batch is also enclosed with the samples for your reference." if draft["coa_enclosed"] else ""}


def letter_payload(draft, supplier_id, supplier_name, with_pdf):
    return {"workflow": "sample_submission", "draft": clean_draft(draft, complete=True),
        "supplier_id": supplier_id, "supplier_name": supplier_name, "with_pdf": with_pdf,
        "template_base64": base64.b64encode(template_bytes()).decode("ascii")}


def regenerate_letter(payload):
    try:
        template = base64.b64decode(payload["template_base64"], validate=True)
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError("The saved sample cover-letter template is missing or invalid.") from exc
    draft = payload["draft"]
    name = filename(draft["reference"])[:25] + "_" + filename(payload.get("supplier_name") or "Samples")[:25] + "_Sample_submission.docx"
    return {name: render_document(template, letter_context(draft))}
