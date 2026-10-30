"""Independent Statement of Compliance form and saved-run generation."""
import base64
from datetime import date
import re

from desktop_paths import asset_root
from documents import filename, render_document

TEMPLATE_NAME = "Statement of Compliance.docx"
FIELDS = {
    "item_number": "Item number",
    "item_name": "Required item / specification *",
    "offered_item": "1. Offered item / specification",
    "required_quantity": "Required quantity",
    "offered_quantity": "2. Offered quantity (include unit)",
    "delivery_schedule": "3. Delivery schedule",
    "packaging": "4. Packaging",
    "payment": "5. Mode of payment",
    "transport": "6. Mode of transport and port of shipment",
    "price_per_kg": "7. C&F price per kg (include currency)",
    "commission": "8. Local agent's commission",
    "total_cost": "9. Total cost (include currency)",
    "total_words": "10. Total cost in words",
    "shelf_life": "11. Shelf life",
    "origin": "12. Country of origin",
    "offer_response": "13. Offered validity / compliance response",
    "sample": "14. Is a sample included?",
    "coa": "15. Certificate of analysis compliance",
    "manufacturer": "16. Manufacturer name and address",
    "manufacturer_phone": "Manufacturer telephone",
    "manufacturer_fax": "Manufacturer fax",
    "manufacturer_email": "Manufacturer email",
    "bidder": "17. Foreign bidder name and address",
    "bidder_phone": "Foreign bidder telephone",
    "bidder_fax": "Foreign bidder fax",
    "bidder_email": "Foreign bidder email",
    "agent": "18. Local agent name and address",
    "agent_phone": "Local agent telephone",
    "agent_fax": "Local agent fax",
    "agent_email": "Local agent email",
    "security": "19. Bid security status, value and method",
}
DEFAULTS = {key: "" for key in FIELDS} | {
    "offer_valid_until": "2027-02-01", "security_valid_until": "2027-03-01",
    "agent": "USECTA (PVT) LTD\n33/5 Boruppa Road, Pallegunnepana,\nGunnepana, Kandy",
    "agent_phone": "0701506081 / 0719451798", "agent_fax": "081 2494518",
    "agent_email": "usectapvtltd@gmail.com",
}


def template_bytes():
    return (asset_root() / "assets" / TEMPLATE_NAME).read_bytes()


def validate_statement(values):
    if not isinstance(values, dict):
        raise ValueError("Enter the statement details.")
    cleaned = {}
    for key, label in FIELDS.items():
        value = values.get(key, "")
        if not isinstance(value, str):
            raise ValueError(f"{label}: enter text.")
        value = value.strip()
        if len(value) > 3000 or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", value):
            raise ValueError(f"{label}: use up to 3,000 characters without control characters.")
        cleaned[key] = value
    if not cleaned["item_name"]:
        raise ValueError("Enter the required item / specification.")
    for key, label in [("offer_valid_until", "Offer validity date"), ("security_valid_until", "Bid security validity date")]:
        try:
            cleaned[key] = date.fromisoformat(str(values.get(key, ""))).isoformat()
        except ValueError as exc:
            raise ValueError(f"{label}: enter a valid date.") from exc
    return cleaned


def statement_files(values, template=None):
    values = validate_statement(values)
    context = dict(values)
    context["supply_item"] = (("ITEM No. " + values["item_number"] + " - ") if values["item_number"] else "") + values["item_name"]
    for key in ("offer_valid_until", "security_valid_until"):
        context[key] = date.fromisoformat(values[key]).strftime("%d.%m.%Y")
    stem = filename("Statement_of_Compliance_" + (values["item_number"] or values["item_name"]))[:75]
    return {stem + ".docx": render_document(template if template is not None else template_bytes(), context)}


def statement_payload(values, with_pdf):
    return {"workflow": "statement_compliance", "values": validate_statement(values),
            "template_base64": base64.b64encode(template_bytes()).decode("ascii"), "with_pdf": with_pdf}


def regenerate_statement(payload):
    try:
        template = base64.b64decode(payload["template_base64"], validate=True)
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError("The saved statement template is missing or invalid.") from exc
    return statement_files(payload["values"], template)
