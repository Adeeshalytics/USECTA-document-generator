"""Local USECTA workspace. Run with python -m streamlit run app.py."""
import hashlib
import json
from datetime import date, time
from pathlib import Path

import streamlit as st

from documents import FIELDS, Store, filename, make_zip, normalize_word, pdf_available, template_variables
from workflows import (QUOTE_COMPUTED, SUPPLIER_FIELDS, TENDER_COMPUTED, choose_items,
                       create_quotation_template, generate_files, import_catalog, long_date,
                       prepare_workspace, quotation_context, quotation_jobs, tender_context, tender_jobs)

st.set_page_config(page_title="USECTA Documents", page_icon="📄", layout="wide")
store = Store()
prepare_workspace(store)
COMPANY = {"company_name": "USECTA (Pvt) Ltd", "company_address": "33/5 Boruppa Road, Pallegunnepana, Gunnepana Kandy"}
SCOPES = {"batch": "One document with the selected item list", "item": "One document per item",
          "supplier": "One agreement for the selected supplier and items", "tender": "One document for the tender (e.g. envelopes)"}
LABELS = FIELDS | SUPPLIER_FIELDS | {
    "quotation_number": "Quotation number", "quotation_expiry_date": "Quotation expiry date",
    "shipment_mode": "Shipment mode", "container_details": "Container details",
    "shipment_quantity": "Shipment quantity / packing summary", "packaging_details": "Packaging details",
    "payment_terms": "Payment terms", "quotation_notes": "Notes",
}


def download_files(files, key):
    for name, content in files.items():
        st.download_button(f"Download {name}", content, file_name=name, key=f"{key}_{name}",
            mime="application/pdf" if name.endswith(".pdf") else "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    st.download_button("Download all as ZIP", make_zip(files), file_name=f"{key}_documents.zip", mime="application/zip", key=f"zip_{key}")


def variables_for(selected):
    used, required = set(), set()
    for template in selected:
        used.update(template_variables(store.template_path(template).read_bytes()))
        required.update(template["required"])
    return used, required


def extra_fields(keys, required, prefix):
    values = {}
    for key in sorted(keys):
        label = LABELS.get(key, key.replace("_", " ").title()) + (" *" if key in required else "")
        widget = st.text_area if "address" in key or "notes" in key or "terms" in key else st.text_input
        values[key] = widget(label, key=f"{prefix}_{key}")
    return values


def generate_panel(workflow, jobs, fingerprint, can_generate, run_name):
    with_pdf = st.checkbox("Include PDF copies", disabled=not pdf_available(), key=f"pdf_{workflow}")
    if not pdf_available():
        st.caption("DOCX works without LibreOffice. Install LibreOffice to enable PDF copies.")
    signature = hashlib.sha256((fingerprint + str(with_pdf)).encode()).hexdigest()
    if st.button("Generate documents", type="primary", disabled=not can_generate, key=f"generate_{workflow}"):
        st.session_state.pop(f"output_{workflow}", None)
        try:
            with st.spinner("Filling your templates…"):
                files = generate_files(store, jobs, with_pdf)
                store.save_record(run_name.strip() or "Untitled run", {"workflow": workflow, "jobs": jobs, "with_pdf": with_pdf})
                st.session_state[f"output_{workflow}"] = {"signature": signature, "files": files}
        except Exception as exc:
            st.error(str(exc))
    output = st.session_state.get(f"output_{workflow}")
    if output and output["signature"] == signature:
        st.success("Documents generated and run details saved. Review wording, item details, and pagination before sending.")
        download_files(output["files"], workflow)


st.title("USECTA document workspace")
st.caption("Your company details stay in your templates. Select a tender and its item numbers, or create a separate quotation.")
with st.sidebar:
    st.header("Saved runs")
    records = store.records()
    by_record = {r["id"]: r for r in records}
    record_id = st.selectbox("Previous document runs", [None] + list(by_record),
        format_func=lambda key: "Choose a saved run" if key is None else f"{by_record[key]['name']} · {by_record[key]['created_at'][:10]}", key="history")
    if record_id:
        record = by_record[record_id]
        payload = json.loads(record["payload"])
        st.download_button("Download saved details", json.dumps(payload, indent=2).encode(), file_name=filename(record["name"]) + ".json", mime="application/json")
        if "jobs" in payload:
            st.caption("Regenerates using the saved item and supplier details, even if the catalogue has since changed.")
            if st.button("Regenerate saved run"):
                try:
                    st.session_state["history_output"] = {"id": record_id, "files": generate_files(store, payload["jobs"], payload.get("with_pdf", False))}
                except Exception as exc:
                    st.error(str(exc))
            saved = st.session_state.get("history_output")
            if saved and saved["id"] == record_id:
                download_files(saved["files"], "history")
        else:
            st.caption("Earlier app record preserved. Download its details to re-enter in the new workflow.")
    st.divider()
    st.caption("Everything is stored locally in data/. Back up that folder. Templates and saved versions are kept unchanged.")
    st.caption("Word output preserves template layout settings. Longer content can change wrapping and page counts; PDF also depends on available fonts.")

tender_tab, quote_tab, catalog_tab, suppliers_tab, templates_tab = st.tabs([
    "Tender documents", "Quotations", "Tenders & items", "Suppliers", "Templates"])

with tender_tab:
    tenders = store.tenders()
    reference = st.selectbox("Tender reference", [None] + list(tenders), format_func=lambda x: x or "Select a tender", key="tender_reference")
    available = [t for t in store.templates() if t["workflow"] == "tender"]
    by_template = {t["id"]: t for t in available}
    selected_ids = st.multiselect("Documents to create", list(by_template), format_func=lambda k: by_template[k]["name"], key="tender_templates")
    selected_templates = [by_template[k] for k in selected_ids]
    used, required = variables_for(selected_templates)
    jobs = []
    if reference:
        tender = tenders[reference]
        st.caption(f"Closing: {tender['closing_date']} at {tender['closing_time']} · Bid validity: {tender.get('bid_valid_until') or 'not specified'}")
        if "bid_valid_until" in required and not tender.get("bid_valid_until"):
            st.warning("The Bid Form needs a bid acceptance validity date. Set it in Tenders & items before generating that form, or deselect the Bid Form to generate your other documents.")
        catalog = {r["item_number"]: r for r in store.catalog(reference)}
        numbers = st.multiselect("Item numbers — search or select", list(catalog),
            format_func=lambda n: f"{n} — {catalog[n]['description']}", key=f"selected_items_{reference}")
        rows = choose_items(store, reference, numbers)
        if rows:
            st.dataframe(rows, hide_index=True, width="stretch", column_config={
                "item_number": "Item number", "description": "Official description", "document_fee": "Document fee (LKR)", "quantity_kg": "Tender quantity (kg)"})
        else:
            st.info("Select item numbers for letters and agreements. Envelopes can be generated without selecting items.")
        suppliers = store.suppliers()
        supplier_id = st.selectbox("Supplier for these items", [None] + list(suppliers),
            format_func=lambda key: "No supplier selected" if key is None else suppliers[key]["supplier_name"], key="tender_supplier")
        supplier = suppliers.get(supplier_id, {})
        st.caption("Select only the items supplied by this supplier. Repeat for another supplier. Collection and personnel letters can include items across suppliers.")
        a, b = st.columns(2)
        document_date = a.date_input("Letter / bid form date", key="tender_document_date")
        effective_date = b.date_input("Agreement effective date", key="tender_effective_date")
        context = tender_context(reference, tender, rows, supplier, document_date, effective_date) | COMPANY
        extra = used - set(context)
        if extra:
            st.subheader("Additional fields in your templates")
            context.update(extra_fields(extra, required, "tender_extra"))
        st.caption("Cover letters and bid forms generate one file per selected item. The agency agreement covers the selected supplier and item list.")
        try:
            jobs = tender_jobs(store, selected_ids, context)
        except ValueError as exc:
            st.warning(str(exc))
        run_name = st.text_input("Save this run as", value=reference, key=f"tender_run_{reference}")
        generate_panel("tender", jobs, json.dumps(jobs, sort_keys=True) + run_name, bool(jobs), run_name)
    else:
        st.info("First save a tender and its item catalogue in Tenders & items. Then select its reference here.")
    if not available:
        st.info("Upload your six Word templates in Templates and choose Tender as their workflow.")

with quote_tab:
    st.subheader("Independent quotations")
    st.caption("Quotation products and row numbers are independent of SPMC tenders. Enter any product and unit here.")
    available = [t for t in store.templates() if t["workflow"] == "quotation"]
    by_quote = {t["id"]: t for t in available}
    ids = st.multiselect("Quotation templates", list(by_quote), default=[available[0]["id"]] if available else [],
        format_func=lambda k: by_quote[k]["name"], key="quotation_templates")
    used, required = variables_for([by_quote[k] for k in ids])
    left, right = st.columns(2)
    number = left.text_input("Quotation number *", key="quotation_number", placeholder="QT-00282")
    currency = right.text_input("Currency *", value="USD", key="quotation_currency")
    issued = left.date_input("Quotation date", key="quotation_date")
    expiry = right.date_input("Quotation expiry date", key="quotation_expiry")
    fields = COMPANY | {"quotation_number": number, "currency": currency, "document_date": long_date(issued), "quotation_expiry_date": long_date(expiry)}
    fields.update(extra_fields(used - set(fields) - QUOTE_COMPUTED, required, "quote"))
    rows = st.data_editor([{"description": "", "quantity": 0.0, "unit": "", "unit_price": 0.0}],
        num_rows="dynamic", hide_index=True, width="stretch", key="quotation_rows", column_config={
            "description": st.column_config.TextColumn("Description"), "unit": st.column_config.TextColumn("Unit (MT, kg, pcs…)"),
            "quantity": st.column_config.NumberColumn("Quantity", min_value=0, step=0.01),
            "unit_price": st.column_config.NumberColumn("Unit price", min_value=0, step=0.01, format="%.2f")})
    jobs = []
    try:
        if expiry < issued:
            raise ValueError("Quotation expiry cannot be before its issue date.")
        context = quotation_context(fields, rows)
        st.metric(f"Total ({currency})", context["grand_total"])
        jobs = quotation_jobs(store, ids, context)
    except ValueError as exc:
        st.warning(str(exc))
    st.caption("Prices and totals round to two decimal places. No tax or currency conversion is applied automatically.")
    generate_panel("quotation", jobs, json.dumps(jobs, sort_keys=True), bool(jobs), number or "Quotation")

with catalog_tab:
    st.subheader("Save each tender once")
    tenders = store.tenders()
    editing = st.selectbox("Create or edit tender", [None] + list(tenders), format_func=lambda x: x or "New tender", key="edit_tender")
    current = tenders.get(editing, {})
    prefix = editing or "new"
    with st.form(f"tender_metadata_{prefix}"):
        ref = st.text_input("Tender reference *", value=editing or "", disabled=bool(editing), key=f"catalog_ref_{prefix}")
        title = st.text_input("Tender title", value=current.get("tender_title", "PROCUREMENT OF PHARMACEUTICAL RAW MATERIALS"), key=f"catalog_title_{prefix}")
        left, right = st.columns(2)
        closing = left.date_input("Closing date *", value=date.fromisoformat(current["closing_date"]) if current else date.today(), key=f"catalog_date_{prefix}")
        clock = right.time_input("Closing time *", value=time.fromisoformat(current.get("closing_time", "10:00")), key=f"catalog_time_{prefix}")
        has_validity = st.checkbox("Specify bid acceptance validity date", value=bool(current.get("bid_valid_until")), key=f"catalog_has_validity_{prefix}")
        validity = st.date_input("Bid acceptance validity date", value=date.fromisoformat(current["bid_valid_until"]) if current.get("bid_valid_until") else closing, key=f"catalog_validity_{prefix}")
        if st.form_submit_button("Save tender"):
            try:
                store.save_tender(ref, {"tender_title": title, "closing_date": closing.isoformat(), "closing_time": clock.strftime("%H:%M"), "bid_valid_until": validity.isoformat() if has_validity else ""})
                st.success("Tender saved. Select it below to add its catalogue.")
            except ValueError as exc:
                st.error(str(exc))
    references = list(store.tenders())
    catalog_ref = st.selectbox("Tender catalogue to edit", [None] + references, format_func=lambda x: x or "Choose a saved tender", key="catalog_reference")
    st.download_button("Download blank CSV format", b"item_number,description,document_fee,quantity_kg\n", file_name="tender_catalogue.csv", mime="text/csv")
    st.caption("Required CSV/XLSX headers: item_number, description, document_fee. Optional: quantity_kg. Document fee is in LKR, separate from product price and bid security. Item numbers are scoped to this tender.")
    bundled = Path(__file__).parent / "catalogues" / "SPMC_03_2026.csv"
    if bundled.exists():
        st.download_button("Download supplied SPMC/03/2026 catalogue (50 items)", bundled.read_bytes(), file_name=bundled.name, mime="text/csv")
    if catalog_ref:
        upload = st.file_uploader("Import item catalogue", type=["csv", "xlsx"], key=f"catalog_upload_{catalog_ref}")
        if upload and st.button("Preview imported catalogue", key=f"preview_{catalog_ref}"):
            try:
                imported = import_catalog(upload.getvalue(), Path(upload.name).suffix)
                st.session_state[f"catalog_stage_{catalog_ref}"] = imported
                st.session_state[f"catalog_revision_{catalog_ref}"] = st.session_state.get(f"catalog_revision_{catalog_ref}", 0) + 1
            except Exception as exc:
                st.error(f"Check your catalogue: {exc}")
        if catalog_ref == "SPMC/03/2026" and not store.catalog(catalog_ref) and bundled.exists() and st.button("Load supplied 50-item catalogue for SPMC/03/2026"):
            st.session_state[f"catalog_stage_{catalog_ref}"] = import_catalog(bundled.read_bytes(), ".csv")
            st.session_state[f"catalog_revision_{catalog_ref}"] = st.session_state.get(f"catalog_revision_{catalog_ref}", 0) + 1
        initial = st.session_state.get(f"catalog_stage_{catalog_ref}", store.catalog(catalog_ref)) or [{"item_number": "", "description": "", "document_fee": "", "quantity_kg": ""}]
        revision = st.session_state.get(f"catalog_revision_{catalog_ref}", 0)
        edited = st.data_editor(initial, num_rows="dynamic", hide_index=True, width="stretch", key=f"catalog_editor_{catalog_ref}_{revision}",
            column_config={"item_number": st.column_config.TextColumn("Item number"), "description": st.column_config.TextColumn("Official item description"), "document_fee": st.column_config.TextColumn("Document fee (LKR)"), "quantity_kg": st.column_config.TextColumn("Tender quantity (kg)")})
        st.caption("Saving replaces this tender's catalogue with the rows shown. Other tenders and saved document runs remain unchanged.")
        if st.button("Save item catalogue", key=f"save_catalog_{catalog_ref}"):
            try:
                store.save_catalog(catalog_ref, edited)
                st.session_state.pop(f"catalog_stage_{catalog_ref}", None)
                st.session_state[f"catalog_revision_{catalog_ref}"] = revision + 1
                st.session_state["catalog_saved"] = catalog_ref
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        if st.session_state.get("catalog_saved") == catalog_ref:
            st.success("Item catalogue saved.")

with suppliers_tab:
    st.subheader("Reusable supplier profiles")
    suppliers = store.suppliers()
    editing = st.selectbox("Create or edit supplier", [None] + list(suppliers), format_func=lambda key: "New supplier" if key is None else suppliers[key]["supplier_name"], key="edit_supplier")
    current = suppliers.get(editing, {})
    with st.form(f"supplier_{editing or 'new'}"):
        fields = {}
        for key, label in SUPPLIER_FIELDS.items():
            widget = st.text_area if key.endswith("address") else st.text_input
            fields[key] = widget(label + (" *" if key == "supplier_name" else ""), value=current.get(key, ""), key=f"supplier_{editing or 'new'}_{key}")
        if st.form_submit_button("Save supplier"):
            try:
                store.save_supplier(fields, editing)
                st.session_state["supplier_saved"] = True
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    if st.session_state.pop("supplier_saved", False):
        st.success("Supplier profile saved.")

with templates_tab:
    st.subheader("Your original Word layouts")
    st.write("Upload DOCX or DOTX templates with placeholders. USECTA's name, address, letterhead, and fixed wording can stay as ordinary text.")
    st.caption("Every upload is a separate version. The generator fills the existing Word package; it does not rebuild the letterhead, tables, styles, or page setup.")
    with st.expander("Placeholder and scope guide"):
        st.code("{%tr for item in tender_items %}\n{{ item.item_number }} | {{ item.description }} | {{ item.document_fee }}\n{%tr endfor %}")
        st.code("{%p for item in tender_items %}\n{{ item.item_number }} – {{ item.description }}\n{%p endfor %}")
        st.write("Table control tags need separate rows. Paragraph control tags need separate paragraphs (Enter, not Shift+Enter).")
        st.write("Use 'One document per item' for cover letters and bid forms. Use the selected list for collection and personnel letters, supplier scope for agreements, and tender scope for envelopes.")
        st.code("Quotation table: quotation_items\n{{ item.number }} | {{ item.description }} | {{ item.quantity }} | {{ item.unit }} | {{ item.unit_price }} | {{ item.total }}")
    upload = st.file_uploader("Upload template", type=["docx", "dotx"], key="template_upload")
    if upload:
        try:
            content = normalize_word(upload.getvalue())
            variables = sorted(template_variables(content))
            st.write("Detected fields: " + (", ".join(variables) or "No placeholders found"))
            name = st.text_input("Template name", value=Path(upload.name).stem, key=f"template_name_{upload.name}")
            workflow = st.selectbox("Document workflow", ["tender", "quotation"], key="template_workflow")
            inferred = "item" if {"item_number", "item_description"} & set(variables) else "supplier" if "agreement_item_names" in variables else "tender" if "tender_items" not in variables else "batch"
            scope = st.selectbox("Output scope", list(SCOPES), index=list(SCOPES).index(inferred), format_func=lambda x: SCOPES[x], key=f"scope_{upload.name}") if workflow == "tender" else "batch"
            mandatory = st.multiselect("Required fields", variables, default=variables, key=f"required_{upload.name}")
            if st.button("Add template version", disabled=not variables):
                if workflow == "quotation" and set(variables) & TENDER_COMPUTED:
                    raise ValueError("This template contains tender fields. Choose Tender, or remove those fields for a quotation.")
                store.add_template(name, content, mandatory, workflow=workflow, scope=scope)
                st.rerun()
        except Exception as exc:
            st.error(f"Check your template: {exc}")
    for template in store.templates():
        with st.expander(f"{template['name']} · {template['workflow']} · {template['created_at'][:10]} · {template['id'][:8]}"):
            st.caption("Required: " + ", ".join(template["required"]))
            st.download_button("Download editable template", store.template_path(template).read_bytes(), file_name=filename(template["name"]) + ".docx", key=f"download_template_{template['id']}")
            with st.form(f"usage_{template['id']}"):
                workflow = st.selectbox("Use in", ["legacy", "tender", "quotation"], index=["legacy", "tender", "quotation"].index(template["workflow"]), key=f"usage_workflow_{template['id']}")
                scope = st.selectbox("Scope", list(SCOPES), index=list(SCOPES).index(template["scope"]), format_func=lambda x: SCOPES[x], key=f"usage_scope_{template['id']}")
                if st.form_submit_button("Save template usage"):
                    store.set_template_usage(template["id"], workflow, scope)
                    st.rerun()
