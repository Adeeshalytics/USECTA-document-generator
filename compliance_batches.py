"""Supplier drafts, schedule defaults and multi-item compliance statements."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import lru_cache
import hashlib
import json
import re

from desktop_paths import asset_root
from documents import filename
from statement_compliance import DEFAULTS, validate_statement, template_bytes

ITEM_FIELDS = {"item_number", "item_name", "offered_item", "required_quantity", "offered_quantity",
               "delivery_schedule", "packaging", "transport", "price_per_kg", "commission",
               "total_cost", "total_words", "security"}
SHARED_FIELDS = (set(DEFAULTS) - ITEM_FIELDS) | {"currency", "default_transport", "security_status"}
SHARED_DEFAULTS = {key: value for key, value in DEFAULTS.items() if key in SHARED_FIELDS} | {
    "payment": "L/C at Sight", "sample": "Yes", "offer_response": "Yes", "coa": "Yes - COA Complies",
    "currency": "USD", "default_transport": "", "security_status": "",
}
SCHEDULE_FILES = {"SPMC/03/2026": "SPMC_03_2026_compliance.json"}
CENT = Decimal("0.01")


@lru_cache(maxsize=8)
def _read_schedule(path):
    return json.loads(path.read_text(encoding="utf-8"))


def schedule_for(reference):
    name = SCHEDULE_FILES.get(reference)
    if not name:
        return {}
    path = asset_root() / "catalogues" / name
    return deepcopy(_read_schedule(path)["items"])


def item_defaults(item, schedule=None):
    schedule = schedule or {}
    quantity = str(schedule.get("quantity_kg", item.get("quantity_kg", "")))
    name = schedule.get("item_name", item["description"])
    return {"item_number": item["item_number"], "item_name": name, "offered_item": name,
            "quantity_kg": quantity, "required_quantity_kg": quantity,
            "delivery_schedule": schedule.get("delivery_schedule", ""),
            "packaging": schedule.get("packaging", ""), "transport": schedule.get("required_transport", ""),
            "price_per_kg": "", "commission": "", "total_override": "", "total_words_override": "",
            "bid_security_lkr": schedule.get("bid_security_lkr", ""), "security_override": ""}


def supplier_draft(supplier, reference):
    settings = supplier.get("statement_compliance", {})
    saved = settings.get("drafts", {}).get(reference)
    if saved:
        return deepcopy(saved)
    shared = deepcopy(SHARED_DEFAULTS) | settings.get("shared", {})
    shared["bidder"] = "\n".join(filter(None, [supplier.get("supplier_name", ""), supplier.get("supplier_address", "")]))
    # Preserve a saved, deliberately edited bidder address, including its contacts.
    shared.update({k: v for k, v in settings.get("shared", {}).items() if k.startswith("bidder")})
    if not shared["origin"]:
        shared["origin"] = supplier.get("supplier_country", "")
    return {"version": 2, "reference": reference, "shared": shared, "selected_items": [], "items": {}}


def draft_signature(draft):
    content = {k: draft.get(k) for k in ("version", "reference", "shared", "selected_items", "items")}
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def save_supplier_draft(store, supplier_id, draft):
    """Save unfinished work independently of generation, preserving all supplier metadata."""
    supplier = store.suppliers().get(supplier_id)
    if supplier is None:
        raise ValueError("Choose or create a supplier before saving changes.")
    if not isinstance(draft.get("reference"), str) or not draft["reference"].strip():
        raise ValueError("Choose a tender before saving changes.")
    if draft.get("version") != 2 or not isinstance(draft.get("shared"), dict) or not isinstance(draft.get("items"), dict):
        raise ValueError("The supplier draft is invalid.")
    selected = draft.get("selected_items")
    if not isinstance(selected, list) or len(selected) > 100 or len(set(selected)) != len(selected):
        raise ValueError("Select up to 100 distinct items.")
    if any(number not in draft["items"] for number in selected):
        raise ValueError("A selected item's details are missing.")
    # Drafts may contain incomplete prices, but must be bounded plain JSON text.
    content = json.dumps(draft, ensure_ascii=False)
    if len(content.encode()) > 2 * 1024 * 1024:
        raise ValueError("The supplier draft is too large.")
    for value in list(draft["shared"].values()) + [v for row in draft["items"].values() for v in row.values()]:
        if not isinstance(value, str) or len(value) > 3000 or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", value):
            raise ValueError("Use plain text of up to 3,000 characters in each field.")
    saved = deepcopy(draft)
    saved["updated_at"] = datetime.now(timezone.utc).isoformat()
    settings = deepcopy(supplier.get("statement_compliance", {}))
    settings["shared"] = {key: value for key, value in saved["shared"].items()
                          if key in SHARED_FIELDS and not key.endswith("_valid_until")}
    settings.setdefault("drafts", {})[draft["reference"]] = saved
    store.save_supplier(supplier | {"statement_compliance": settings}, supplier_id)
    return saved


def decimal_value(value, label, allow_empty=False):
    value = str(value).strip().replace(",", "")
    if not value and allow_empty:
        return None
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{label}: enter a number.") from exc
    if not number.is_finite() or number < 0 or number >= Decimal("1000000000000"):
        raise ValueError(f"{label}: enter a non-negative number below one trillion.")
    if number.as_tuple().exponent < -12:
        raise ValueError(f"{label}: use at most 12 decimal places.")
    return number


def _integer_words(number):
    small = ("Zero One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve Thirteen Fourteen Fifteen Sixteen Seventeen Eighteen Nineteen").split()
    tens = ("Zero Ten Twenty Thirty Forty Fifty Sixty Seventy Eighty Ninety").split()
    if number < 20:
        return small[number]
    if number < 100:
        return tens[number // 10] + (" " + small[number % 10] if number % 10 else "")
    if number < 1000:
        return small[number // 100] + " Hundred" + (" " + _integer_words(number % 100) if number % 100 else "")
    for scale, name in [(10**9, "Billion"), (10**6, "Million"), (1000, "Thousand")]:
        if number >= scale:
            return _integer_words(number // scale) + " " + name + (" " + _integer_words(number % scale) if number % scale else "")


def amount_in_words(amount, currency):
    amount = decimal_value(amount, "Total cost").quantize(CENT, rounding=ROUND_HALF_UP)
    whole, cents = int(amount), int((amount % 1) * 100)
    major, minor = {"USD": ("United States Dollar", "Cent"), "EUR": ("Euro", "Cent"),
                    "GBP": ("Pound Sterling", "Penny"), "LKR": ("Sri Lankan Rupee", "Cent")}.get(currency, (currency, "Cent"))
    major_plural = "Pounds Sterling" if currency == "GBP" else major + "s"
    minor_plural = "Pence" if currency == "GBP" else minor + "s"
    result = _integer_words(whole) + " " + (major if whole == 1 else major_plural)
    if cents:
        result += " and " + _integer_words(cents) + " " + (minor if cents == 1 else minor_plural)
    return result


def item_totals(row, currency):
    prefix = "Item " + row["item_number"]
    price = decimal_value(row.get("price_per_kg", ""), prefix + " C&F price", allow_empty=True)
    quantity = decimal_value(row.get("quantity_kg", ""), prefix + " quantity", allow_empty=True)
    override = decimal_value(row.get("total_override", ""), prefix + " total override", allow_empty=True)
    if override is not None:
        total = override.quantize(CENT, rounding=ROUND_HALF_UP)
    elif price is not None and quantity is not None:
        total = (price * quantity).quantize(CENT, rounding=ROUND_HALF_UP)
    else:
        total = None
    if total is not None and total >= Decimal("1000000000000"):
        raise ValueError(prefix + ": total must be below one trillion.")
    words = row.get("total_words_override", "").strip()
    if not words and total is not None:
        words = amount_in_words(str(total), currency)
    return price, total, words


def batch_values(draft):
    numbers = draft.get("selected_items", [])
    if not numbers:
        raise ValueError("Select at least one item for this supplier.")
    if len(numbers) > 100 or len(set(numbers)) != len(numbers):
        raise ValueError("Select up to 100 distinct items.")
    shared = SHARED_DEFAULTS | draft["shared"]
    currency = shared["currency"].strip().upper()
    if currency not in {"USD", "EUR", "GBP", "LKR"}:
        raise ValueError("Choose USD, EUR, GBP or LKR as the quotation currency.")
    statements = []
    schedule = schedule_for(draft.get("reference", ""))
    for number in numbers:
        row = draft["items"][number]
        if schedule.get(number, {}).get("required_transport") == "By Air" and "air" not in row.get("transport", "").lower():
            raise ValueError(f"Item {number}: the schedule requires delivery by air. Set entry 6 to include air transport.")
        price, total, words = item_totals(row, currency)
        if price is None:
            raise ValueError(f"Item {number}: enter the C&F price per kg. You can save unfinished changes first.")
        quantity = decimal_value(row["quantity_kg"], f"Item {number} quantity")
        if quantity <= 0:
            raise ValueError(f"Item {number}: quantity must be greater than zero.")
        quantity_text = f"{quantity:,.12f}".rstrip("0").rstrip(".") + " kg"
        required_quantity = decimal_value(row.get("required_quantity_kg", row["quantity_kg"]), f"Item {number} required quantity")
        required_text = f"{required_quantity:,.12f}".rstrip("0").rstrip(".") + " kg"
        security = row.get("security_override", "").strip()
        if not security and row.get("bid_security_lkr", "").strip():
            security = "SL Rs. " + f"{decimal_value(row['bid_security_lkr'], 'Bid security'):,.2f}"
        if shared["security_status"].strip():
            security += (" - " if security else "") + shared["security_status"].strip()
        values = DEFAULTS | {k: v for k, v in shared.items() if k in DEFAULTS}
        values.update({k: row.get(k, "") for k in ("item_number", "item_name", "offered_item", "delivery_schedule", "packaging", "transport", "commission")})
        values.update(required_quantity=required_text, offered_quantity=quantity_text,
                      price_per_kg=currency + " " + format(price, "f") + " / kg",
                      total_cost=currency + " " + f"{total:,.2f}", total_words=words, security=security)
        statements.append(validate_statement(values))
    return statements


def batch_payload(draft, supplier_id, supplier_name, with_pdf):
    import base64
    return {"workflow": "statement_compliance", "version": 2, "supplier_id": supplier_id,
            "supplier_name": supplier_name, "reference": draft["reference"], "draft": deepcopy(draft),
            "statements": batch_values(draft), "with_pdf": with_pdf,
            "template_base64": base64.b64encode(template_bytes()).decode("ascii")}


def batch_filename(reference, supplier, number):
    return "_".join([filename(reference)[:22], filename(supplier)[:25], "Compliance_item", filename(number)[:18]]) + ".docx"
