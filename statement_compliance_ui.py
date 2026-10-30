"""Fast supplier-based batch editing and persistent compliance drafts."""
from copy import deepcopy
from datetime import date
import hashlib
import logging
import uuid

import streamlit as st

import documents
from compliance_batches import (SHARED_DEFAULTS, batch_payload, batch_values, draft_signature,
                                item_defaults, item_totals, save_supplier_draft, schedule_for, supplier_draft)
from statement_compliance import FIELDS, regenerate_statement, template_bytes

GRID_FIELDS = ("transport", "price_per_kg", "commission", "total_override")


def _remember(key):
    st.session_state.setdefault("_compliance_input_keys", set()).add(key)
    return key


def queue_statement_edit(payload):
    st.session_state["_compliance_import"] = deepcopy(payload)
    st.session_state["page"] = "Statement of Compliance"


def _grid_changes(context, editor_key, numbers):
    """Commit a cell before switching supplier, item selection or page."""
    draft = st.session_state["_compliance_batches"][context]
    changes = st.session_state.get(editor_key, {}).get("edited_rows", {})
    for index, edits in changes.items():
        if 0 <= int(index) < len(numbers):
            row = draft["items"][numbers[int(index)]]
            row.update({key: str(value or "") for key, value in edits.items() if key in GRID_FIELDS})


def render_statement_compliance(store, cloud_mode, download_files):
    st.subheader("Statement of Compliance")
    st.caption("Choose a supplier, select all their items, then enter the item prices. Shared details are entered once. Save unfinished changes or download one statement per item together.")
    suppliers, tenders = store.suppliers(), store.tenders()
    pending = st.session_state.pop("_compliance_import", None)
    if pending:
        sid, ref = pending.get("supplier_id"), pending.get("reference")
        if sid in suppliers and ref in tenders:
            st.session_state["compliance_supplier"] = sid
            st.session_state["compliance_reference"] = ref
            context = hashlib.sha256((sid + "\n" + ref).encode()).hexdigest()[:16]
            st.session_state.setdefault("_compliance_batches", {})[context] = deepcopy(pending["draft"])
            for key in list(st.session_state.get("_compliance_input_keys", set())):
                if key.startswith("compliance_" + context + "_"):
                    st.session_state.pop(key, None)
            st.session_state.setdefault("_compliance_grid", {}).pop(context, None)
        else:
            st.warning("The saved run's supplier or tender is no longer available. Its original documents can still be regenerated in Saved runs.")
    chosen = st.session_state.pop("_compliance_choose_supplier", None)
    if chosen:
        st.session_state["compliance_supplier"] = chosen
    if st.session_state.get("compliance_supplier") not in suppliers:
        st.session_state["compliance_supplier"] = None
    if st.session_state.get("compliance_reference") not in tenders:
        st.session_state["compliance_reference"] = "SPMC/03/2026" if "SPMC/03/2026" in tenders else next(iter(tenders), None)
    left, right = st.columns(2)
    with left:
        supplier_id = st.selectbox("Supplier", [None] + list(suppliers),
            format_func=lambda key: "Choose a supplier" if key is None else suppliers[key]["supplier_name"], key=_remember("compliance_supplier"))
    with right:
        reference = st.selectbox("Tender", list(tenders), key=_remember("compliance_reference"))
    with st.expander("Add a new supplier"):
        with st.form("soc_create_supplier"):
            name = st.text_input("New supplier name", key="soc_new_supplier_name")
            if st.form_submit_button("Create supplier"):
                try:
                    sid = store.save_supplier({"supplier_name": name})
                    st.session_state["_compliance_choose_supplier"] = sid
                    st.rerun()
                except (ValueError, RuntimeError) as error:
                    st.error(str(error))
    if not supplier_id or not reference:
        st.info("Choose a saved supplier above, or add one here to start. Your items, prices and shared details will be saved with that supplier.")
        return
    supplier = suppliers[supplier_id]
    context = hashlib.sha256((supplier_id + "\n" + reference).encode()).hexdigest()[:16]
    drafts = st.session_state.setdefault("_compliance_batches", {})
    if context not in drafts:
        drafts[context] = supplier_draft(supplier, reference)
    draft = drafts[context]
    saved = supplier.get("statement_compliance", {}).get("drafts", {}).get(reference)
    catalogue = {row["item_number"]: row for row in store.catalog(reference)}
    schedule = schedule_for(reference)

    def widget_key(field):
        return _remember(f"compliance_{context}_{field}")

    selection_key = widget_key("selected")
    st.session_state.setdefault(selection_key, list(draft["selected_items"]))
    # Saved snapshots remain selectable if the live catalogue is later changed.
    options = list(catalogue) + [n for n in draft["items"] if n not in catalogue]
    selected = st.multiselect("Items supplied by this supplier", options,
        format_func=lambda number: f"{number} - " + (draft["items"][number]["item_name"] if number in draft["items"] else schedule.get(number, {}).get("item_name", catalogue[number]["description"])),
        key=selection_key)
    draft["selected_items"] = selected
    for number in selected:
        if number not in draft["items"]:
            draft["items"][number] = item_defaults(catalogue[number], schedule.get(number))
            if not draft["items"][number]["transport"]:
                draft["items"][number]["transport"] = draft["shared"].get("default_transport", "")
    st.caption("Quantity, delivery, packaging and bid-security values are prefilled from the supplied SPMC/03/2026 schedule. Other tenders use their own catalogue and manual schedule details.")
    save_top = st.button("Save changes", key="soc_save_top", help="Save all supplier details, selected items and prices, including unfinished work.")

    if selected:
        st.markdown("**Item prices and shipment details**")
        st.caption("6-9: edit these cells for each item. Prices are per kg in the currency below. Leave Total override blank to calculate quantity × C&F price; commission is recorded separately and is not added to that total.")
        grid_cache = st.session_state.setdefault("_compliance_grid", {})
        state = grid_cache.get(context)
        if state is None or state["numbers"] != selected or state["key"] not in st.session_state:
            revision = st.session_state.get("_compliance_grid_revision", 0) + 1
            st.session_state["_compliance_grid_revision"] = revision
            state = {"numbers": list(selected), "key": f"soc_grid_{context}_{revision}",
                     "rows": [{key: draft["items"][number].get(key, "") for key in ("item_number", "item_name") + GRID_FIELDS} for number in selected]}
            grid_cache[context] = state
        edited = st.data_editor(state["rows"], key=state["key"], hide_index=True, width="stretch",
            num_rows="fixed", disabled=["item_number", "item_name"], height=min(420, 40 + 35 * len(selected)),
            column_config={
                "item_number": st.column_config.TextColumn("Item", width="small"),
                "item_name": st.column_config.TextColumn("Product", width="medium"),
                "transport": st.column_config.TextColumn("6. Transport / port", width="medium"),
                "price_per_kg": st.column_config.TextColumn("7. C&F / kg", width="small"),
                "commission": st.column_config.TextColumn("8. Commission", width="small", help="Include %, e.g. 7%"),
                "total_override": st.column_config.TextColumn("9. Total override", width="small", help="Optional numeric total; blank calculates it automatically"),
            }, on_change=_grid_changes, args=(context, state["key"], list(selected)))
        for row in edited:
            draft["items"][row["item_number"]].update({key: str(row.get(key) or "") for key in GRID_FIELDS})

    def shared_field(field, multiline=False, label=None):
        key = widget_key(field)
        st.session_state.setdefault(key, draft["shared"].get(field, SHARED_DEFAULTS.get(field, "")))
        widget = st.text_area if multiline else st.text_input
        draft["shared"][field] = widget(label or FIELDS.get(field, field.replace("_", " ").title()), key=key)

    with st.expander("Supplier details and common responses - apply to every selected item", expanded=not bool(saved)):
        left, right = st.columns(2)
        with left:
            currency_key = widget_key("currency")
            st.session_state.setdefault(currency_key, draft["shared"].get("currency", "USD"))
            draft["shared"]["currency"] = st.selectbox("Quotation currency", ["USD", "EUR", "GBP", "LKR"], key=currency_key)
            shared_field("default_transport", label="Usual transport / port for new items")
            shared_field("payment")
            shared_field("shelf_life")
            shared_field("origin")
            shared_field("security_status", label="Bid security status / method (applies to each item's value)")
        with right:
            shared_field("offer_response")
            shared_field("sample")
            shared_field("coa")
            for field, label in [("offer_valid_until", "Required offer validity up to"), ("security_valid_until", "Required bid security validity up to")]:
                key = widget_key(field)
                if key not in st.session_state:
                    try:
                        st.session_state[key] = date.fromisoformat(draft["shared"].get(field, SHARED_DEFAULTS[field]))
                    except ValueError:
                        st.session_state[key] = None
                draft["shared"][field] = str(st.date_input(label, key=key))
            st.caption("The blank form starts with 1 February 2027 / 1 March 2027 and states 91 / 119 days. Confirm the dates for this tender.")
        for column, party in zip(st.columns(3), ("manufacturer", "bidder", "agent")):
            with column:
                shared_field(party, True)
                for suffix in ("phone", "fax", "email"):
                    shared_field(party + "_" + suffix)
        st.caption("Save changes keeps these details for this supplier and restores the selected items and their individual prices next time.")
        if st.button("Apply usual transport to selected items", key="soc_apply_transport", disabled=not selected):
            for number in selected:
                if schedule.get(number, {}).get("required_transport") != "By Air":
                    draft["items"][number]["transport"] = draft["shared"]["default_transport"]
            st.session_state.setdefault("_compliance_grid", {}).pop(context, None)
            st.rerun()

    if selected:
        with st.expander("Check or adjust schedule details for an item"):
            detail_key = widget_key("detail_item")
            if st.session_state.get(detail_key) not in selected:
                st.session_state[detail_key] = selected[0]
            number = st.selectbox("Item to review", selected, key=detail_key)
            row = draft["items"][number]
            details = schedule.get(number, {})
            st.write(row["item_name"])
            for field, label, multiline in [
                ("offered_item", "1. Offered item / specification", True), ("quantity_kg", "2. Offered quantity in kg", False),
                ("delivery_schedule", "3. Delivery schedule", True), ("packaging", "4. Packaging", True),
                ("bid_security_lkr", "19. Required bid security value (LKR)", False),
                ("security_override", "19. Alternative bid security wording (optional)", False),
                ("total_words_override", "10. Alternative total in words (optional)", True),
            ]:
                key = widget_key(number + "_" + field)
                st.session_state.setdefault(key, row.get(field, ""))
                row[field] = (st.text_area if multiline else st.text_input)(label, key=key)
            if details:
                st.caption("Required shelf life: " + details["shelf_life_requirement"])
                st.caption("Required sample quantity: " + details["sample_quantity"])
                st.caption(f"Schedule source: PDF page {details['source_page']}.")
                st.text(details["specifications"])

    totals, errors = [], []
    for number in selected:
        row = draft["items"][number]
        try:
            _, total, words = item_totals(row, draft["shared"]["currency"])
            totals.append({"Item": number, "Quantity (kg)": row["quantity_kg"],
                "Total": "" if total is None else draft["shared"]["currency"] + f" {total:,.2f}", "Amount in words": words,
                "Bid security (LKR)": row["bid_security_lkr"]})
        except ValueError as error:
            errors.append(str(error))
    if totals:
        st.markdown("**Totals and bid security**")
        st.dataframe(totals, hide_index=True, width="stretch")
    for error in errors:
        st.warning(error)
    can_generate = False
    try:
        batch_values(draft)
        can_generate = True
    except ValueError as error:
        if selected and not errors:
            st.info(str(error))
    unchanged = saved is not None and draft_signature(saved) == draft_signature(draft)
    save_status = st.empty()
    save_status.caption("All changes saved for this supplier and tender." if unchanged else "Unsaved changes - use Save changes to keep this draft, even before all prices are ready.")
    pdf_ready = bool(documents.pdf_available())
    with_pdf = st.checkbox("Include PDF copies", value=pdf_ready, disabled=not pdf_ready, key=widget_key("pdf"))
    if not pdf_ready:
        st.caption("Word downloads are available. PDF needs LibreOffice.")
    signature = hashlib.sha256((context + draft_signature(draft) + str(with_pdf)).encode()).hexdigest()
    save_col, generate_col = st.columns(2)
    with save_col:
        save_clicked = st.button("Save changes", type="primary", key="soc_save")
    with generate_col:
        generate_clicked = st.button(f"Generate {len(selected)} statements", disabled=not can_generate, key="soc_generate")
    if save_clicked or save_top or generate_clicked:
        try:
            saved = save_supplier_draft(store, supplier_id, draft)
            save_status.caption("All changes saved for this supplier and tender.")
            if save_clicked or save_top:
                st.success("Changes saved with " + supplier["supplier_name"] + ". Select this supplier and tender to continue later.")
            if generate_clicked:
                st.session_state.pop("_compliance_output", None)
                with st.spinner("Preparing statements for all selected items…"):
                    payload = batch_payload(draft, supplier_id, supplier["supplier_name"], with_pdf)
                    files = regenerate_statement(payload)
                    warning = ""
                    if with_pdf:
                        try:
                            files.update(documents.convert_pdfs(files))
                        except Exception as error:
                            logging.exception("Compliance PDF conversion failed")
                            warning = str(error)
                    folder = ""
                    if not cloud_mode:
                        destination = store.root / "exports" / ("compliance_" + uuid.uuid4().hex[:8])
                        destination.mkdir(parents=True)
                        for name, content in files.items():
                            (destination / name).write_bytes(content)
                        folder = str(destination)
                        payload["output_directory"] = folder
                    store.save_record(f"Compliance · {supplier['supplier_name']} · {reference} · {len(selected)} items", payload)
                    st.session_state["_compliance_output"] = {"signature": signature, "files": files, "warning": warning, "folder": folder,
                        "zip": documents.make_zip(files)}
        except Exception as error:
            logging.exception("Saving or generating supplier compliance statements failed")
            st.error(str(error))
    output = st.session_state.get("_compliance_output")
    if output and output["signature"] == signature:
        st.success(f"{len(selected)} statements generated and supplier changes saved. Check the documents before signing.")
        if output["warning"]:
            st.warning("Word documents were saved, but PDF conversion failed: " + output["warning"])
        if output["folder"]:
            st.caption("Saved to: " + output["folder"])
        st.download_button("Download all statements (ZIP)", output["zip"],
            file_name=documents.filename(reference + "_" + supplier["supplier_name"]) + "_Compliance.zip",
            mime="application/zip", key="soc_download_all", type="primary")
        with st.expander("Download an individual statement"):
            stems = [name[:-5] for name in output["files"] if name.endswith(".docx")]
            stem = st.selectbox("Choose an item", stems,
                format_func=lambda value: "Item " + value.rsplit("_item_", 1)[-1], key="soc_download_item")
            left, right = st.columns(2)
            for column, extension, mime in [(left, ".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                                            (right, ".pdf", "application/pdf")]:
                name = stem + extension
                if name in output["files"]:
                    with column:
                        st.download_button("Download " + ("Word" if extension == ".docx" else "PDF"), output["files"][name],
                            file_name=name, mime=mime, key="soc_download" + extension)
    st.caption("All table entries are centered horizontally and vertically. The signature and seal area remains empty for signing after printing.")
    with st.expander("Editable form template"):
        st.download_button("Download Word template", template_bytes(), file_name="Statement of Compliance template.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key="soc_download_template")
