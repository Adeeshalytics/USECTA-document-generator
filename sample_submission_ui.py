"""Sample submission letters with supplier/tender drafts and multi-item lists."""
from copy import deepcopy
from datetime import date
import hashlib
import logging
import uuid

import streamlit as st

import documents
from compliance_batches import schedule_for
from sample_submission import (TEXT_DEFAULTS, clean_draft, draft_signature, letter_payload,
                               load_draft, regenerate_letter, save_draft, template_bytes)


def _remember(key):
    st.session_state.setdefault("_sample_submission_input_keys", set()).add(key)
    return key


def queue_submission(supplier_id, reference, items):
    st.session_state["_sample_submission_import"] = {"supplier_id": supplier_id, "reference": reference,
        "items": [{"item_number": row["item_number"], "description": row.get("offered_item") or row["item_name"]} for row in items]}
    st.session_state["page"] = "Sample submission"


def queue_saved_letter(payload):
    st.session_state["_sample_submission_import"] = deepcopy(payload)
    st.session_state["page"] = "Sample submission"


def render_sample_submission(store, cloud_mode, download_files):
    st.subheader("Sample submission cover letter")
    st.caption("One USECTA cover letter listing all selected sample items. Saved compliance items load automatically for a supplier; no prices are needed here.")
    suppliers, tenders = store.suppliers(), store.tenders()
    cache = st.session_state.setdefault("_sample_submission_drafts", {})
    pending = st.session_state.pop("_sample_submission_import", None)
    if pending:
        sid, ref = pending.get("supplier_id"), pending["reference"] if "reference" in pending else pending["draft"]["reference"]
        if (sid is None or sid in suppliers) and ref in tenders:
            st.session_state["sample_submission_supplier"] = sid
            st.session_state["sample_submission_reference"] = ref
            context = hashlib.sha256(((sid or "general") + "\n" + ref).encode()).hexdigest()[:16]
            draft = deepcopy(pending["draft"]) if "draft" in pending else deepcopy(cache.get(context) or load_draft(store, sid, ref))
            if "items" in pending:
                draft["selected_items"] = [row["item_number"] for row in pending["items"]]
                draft["items"].update({row["item_number"]: {k: " ".join(v.split()) for k, v in row.items()} for row in pending["items"]})
            cache[context] = draft
            for key in list(st.session_state.get("_sample_submission_input_keys", set())):
                if key.startswith("sample_letter_" + context + "_"):
                    st.session_state.pop(key, None)
            st.session_state.setdefault("_sample_submission_grids", {}).pop(context, None)
        else:
            st.warning("The saved letter's supplier or tender is no longer available. You can still regenerate its original document from Saved runs.")
    if st.session_state.get("sample_submission_supplier") not in suppliers:
        st.session_state["sample_submission_supplier"] = None
    if st.session_state.get("sample_submission_reference") not in tenders:
        st.session_state["sample_submission_reference"] = "SPMC/03/2026" if "SPMC/03/2026" in tenders else next(iter(tenders), None)
    left, right = st.columns(2)
    with left:
        supplier_id = st.selectbox("Supplier (optional)", [None] + list(suppliers),
            format_func=lambda value: "General submission / multiple suppliers" if value is None else suppliers[value]["supplier_name"],
            key=_remember("sample_submission_supplier"))
    with right:
        reference = st.selectbox("Tender for sample submission", list(tenders), key=_remember("sample_submission_reference"))
    if not reference:
        st.info("Add a tender and its items in Tenders & items first.")
        return
    context = hashlib.sha256(((supplier_id or "general") + "\n" + reference).encode()).hexdigest()[:16]
    if context not in cache:
        cache[context] = load_draft(store, supplier_id, reference)
    draft = cache[context]
    saved = (suppliers[supplier_id].get("sample_submission", {}).get("drafts", {}).get(reference) if supplier_id else store.profiles().get("sample_submission:" + reference))
    catalogue = {row["item_number"]: row for row in store.catalog(reference)}
    schedule = schedule_for(reference)

    def widget_key(field):
        return _remember(f"sample_letter_{context}_{field}")

    selection_key = widget_key("selected")
    st.session_state.setdefault(selection_key, list(draft["selected_items"]))
    options = list(catalogue) + [number for number in draft["items"] if number not in catalogue]
    # Streamlit matches multiselect values against formatted option labels.
    # Keep those labels stable while the editable letter descriptions change.
    labels = st.session_state.setdefault("_sample_submission_option_labels", {}).setdefault(context, {})
    for number in options:
        if number not in labels:
            labels[number] = f"{number} - " + (schedule.get(number, {}).get("item_name", catalogue[number]["description"])
                if number in catalogue else draft["items"][number]["description"])
    selected = st.multiselect("Items included with the samples", options,
        format_func=lambda n: labels[n],
        key=selection_key)
    draft["selected_items"] = selected
    for number in selected:
        if number not in draft["items"]:
            description = schedule.get(number, {}).get("item_name", catalogue[number]["description"])
            draft["items"][number] = {"item_number": number, "description": " ".join(description.split())}
    if selected:
        grids = st.session_state.setdefault("_sample_submission_grids", {})
        state = grids.get(context)
        if state is None or state["numbers"] != selected or state["key"] not in st.session_state:
            revision = st.session_state.get("_sample_submission_revision", 0) + 1
            st.session_state["_sample_submission_revision"] = revision
            state = {"numbers": list(selected), "key": f"sample_letter_grid_{context}_{revision}",
                     "rows": [deepcopy(draft["items"][number]) for number in selected]}
            grids[context] = state
        edited = st.data_editor(state["rows"], key=state["key"], disabled=["item_number"], hide_index=True,
            num_rows="fixed", width="stretch", height=min(420, 40 + 35 * len(selected)),
            column_config={"item_number": st.column_config.TextColumn("Item No.", width="small"),
                           "description": st.column_config.TextColumn("Sample description (editable)", width="large")})
        for row in edited:
            draft["items"][row["item_number"]]["description"] = str(row.get("description") or "")
    left, right = st.columns(2)
    with left:
        key = widget_key("document_date")
        if key not in st.session_state:
            try:
                st.session_state[key] = date.fromisoformat(draft["document_date"])
            except ValueError:
                st.session_state[key] = None
        draft["document_date"] = str(st.date_input("Letter date", key=key))
    with right:
        key = widget_key("packs_per_item")
        st.session_state.setdefault(key, draft["packs_per_item"])
        draft["packs_per_item"] = int(st.number_input("Sample packs per item", min_value=1, max_value=100, step=1, key=key))
    key = widget_key("quantity_note")
    st.session_state.setdefault(key, draft["quantity_note"])
    draft["quantity_note"] = st.text_input("Sample quantity note", key=key)
    key = widget_key("coa_enclosed")
    st.session_state.setdefault(key, draft["coa_enclosed"])
    draft["coa_enclosed"] = st.checkbox("Original Certificate of Analysis is enclosed", key=key)
    st.caption(f"{len(selected)} items · {len(selected) * draft['packs_per_item']} sample packs in total. The letter updates its item count and quantity wording automatically.")
    with st.expander("Recipient and signatory details"):
        for field, label in [("recipient_name", "Recipient"), ("recipient_address", "Recipient address"),
                             ("salutation", "Salutation"), ("signatory_name", "Signatory name"),
                             ("signatory_designation", "Signatory designation")]:
            key = widget_key(field)
            st.session_state.setdefault(key, draft.get(field, TEXT_DEFAULTS[field]))
            draft[field] = (st.text_area if field == "recipient_address" else st.text_input)(label, key=key)
    valid = False
    try:
        clean_draft(draft, complete=True)
        valid = True
    except ValueError as error:
        if selected:
            st.info(str(error))
    unchanged = saved is not None and draft_signature(saved) == draft_signature(draft)
    status = st.empty()
    status.caption("All letter changes saved." if unchanged else "Unsaved letter changes. Save this draft to continue later.")
    pdf_ready = bool(documents.pdf_available())
    with_pdf = st.checkbox("Include PDF copy", value=pdf_ready, disabled=not pdf_ready, key=widget_key("pdf"))
    if not pdf_ready:
        st.caption("Word download is available. PDF copies require LibreOffice.")
    signature = hashlib.sha256((context + draft_signature(draft) + str(with_pdf)).encode()).hexdigest()
    left, right = st.columns(2)
    with left:
        save = st.button("Save letter changes", key="sample_letter_save")
    with right:
        generate = st.button("Generate sample cover letter", type="primary", disabled=not valid, key="sample_letter_generate")
    if save or generate:
        try:
            save_draft(store, supplier_id, draft)
            status.caption("All letter changes saved.")
            if save:
                st.success("Sample cover-letter draft saved. Choose the same supplier and tender to continue later.")
            if generate:
                st.session_state.pop("_sample_submission_output", None)
                with st.spinner("Preparing the sample submission cover letter…"):
                    supplier_name = suppliers[supplier_id]["supplier_name"] if supplier_id else ""
                    payload = letter_payload(draft, supplier_id, supplier_name, with_pdf)
                    files = regenerate_letter(payload)
                    warning = ""
                    if with_pdf:
                        try:
                            files.update(documents.convert_pdfs(files))
                        except Exception as error:
                            logging.exception("Sample cover-letter PDF conversion failed")
                            warning = str(error)
                    if not cloud_mode:
                        destination = store.root / "exports" / ("sample_submission_" + uuid.uuid4().hex[:8])
                        destination.mkdir(parents=True)
                        for name, content in files.items():
                            (destination / name).write_bytes(content)
                        payload["output_directory"] = str(destination)
                    store.save_record("Sample submission · " + reference + (" · " + supplier_name if supplier_name else ""), payload)
                    st.session_state["_sample_submission_output"] = {"signature": signature, "files": files, "warning": warning}
        except Exception as error:
            logging.exception("Saving or generating a sample cover letter failed")
            st.error(str(error))
    output = st.session_state.get("_sample_submission_output")
    if output and output["signature"] == signature:
        st.success("Sample cover letter generated and details saved. Review the sample list and enclosures before signing.")
        if output["warning"]:
            st.warning("Word letter was saved, but PDF conversion failed: " + output["warning"])
        download_files(output["files"], "sample_submission")
    st.caption("Letterhead is preserved. Sign and stamp the letter after printing; the example's handwritten signature and stamp are not reproduced.")
    with st.expander("Editable cover-letter template"):
        st.download_button("Download sample cover-letter template", template_bytes(), file_name="Sample submission cover letter template.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key="sample_letter_template_download")
