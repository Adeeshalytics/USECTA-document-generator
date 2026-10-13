"""Sample labels workflow, independent of bid validity and supplier fields."""
import hashlib
import json
import logging
import uuid

import streamlit as st

import documents
from documents import filename
from sample_labels import LAYOUT_VERSION, label_files, validate_labels


def render_sample_labels(store, cloud_mode, download_files):
    st.subheader("Sample labels")
    st.caption("Two identical labels per product. Every label has its own four borders, with small gaps between labels. Content-sized rows fill pages automatically to save paper.")
    st.info("Print the PDF at Actual size / 100% on Letter paper (8.5 × 11 inches). Do not use Fit to page. Test on plain paper first: label heights vary with their text; this is not a calibrated pre-cut sticker-sheet layout.")
    tenders = store.tenders()
    reference = st.selectbox("Load names from a tender (optional)", [None] + list(tenders),
        format_func=lambda key: "Enter names manually" if key is None else key, key="labels_reference")
    if reference:
        catalogue = {row["item_number"]: row for row in store.catalog(reference)}
        numbers = st.multiselect("Items for sample labels", list(catalogue),
            format_func=lambda number: f"{number} — {catalogue[number]['description']}", key=f"labels_items_{reference}")
        st.caption("Loading fills the fields below. You can edit the exact product names, specifications or IFB number before generating.")
        if st.button("Load selected items into labels", key="labels_load", disabled=not numbers):
            st.session_state["labels_ifb"] = reference
            st.session_state["labels_names"] = "\n".join(" ".join(catalogue[number]["description"].split()) for number in numbers)
            st.session_state.pop("labels_output", None)
    ifb_number = st.text_input("IFB number *", key="labels_ifb", placeholder="SPMC/03/2026")
    names_text = st.text_area("Product names * — one product per line", key="labels_names", height=160,
        placeholder="Enter the full name/specification to print on each product's labels")
    names = [line.strip() for line in names_text.splitlines() if line.strip()]
    valid = False
    try:
        ifb_number, names = validate_labels(ifb_number, names)
        valid = True
        st.caption(f"{len(names)} products · {len(names) * 2} labels. Rows fit their text and fill each sheet automatically; longer names use more space.")
    except ValueError as error:
        if ifb_number or names_text:
            st.warning(str(error))
    with_pdf = st.checkbox("Include print-ready PDF", value=bool(documents.pdf_available()), disabled=not documents.pdf_available(), key="labels_pdf")
    if not documents.pdf_available():
        st.caption("Word output is available. PDF requires the bundled converter or LibreOffice.")
    payload = {"workflow": "sample_labels", "ifb_number": ifb_number, "product_names": names,
               "layout_version": LAYOUT_VERSION, "with_pdf": with_pdf}
    signature = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    if st.button("Generate sample labels", type="primary", disabled=not valid, key="labels_generate"):
        st.session_state.pop("labels_output", None)
        try:
            with st.spinner("Preparing sample labels…"):
                files = label_files(ifb_number, names)
                warning = ""
                if with_pdf:
                    try:
                        files.update(documents.convert_pdfs(files))
                    except Exception as error:
                        logging.exception("Sample label PDF conversion failed")
                        warning = str(error)
                if not cloud_mode:
                    destination = store.root / "exports" / (filename(ifb_number)[:50] + "_labels_" + uuid.uuid4().hex[:8])
                    destination.mkdir(parents=True)
                    for name, content in files.items():
                        (destination / name).write_bytes(content)
                    payload["output_directory"] = str(destination)
                store.save_record("Sample labels · " + ifb_number, payload)
                st.session_state["labels_output"] = {"signature": signature, "files": files, "warning": warning}
        except Exception as error:
            logging.exception("Sample label generation failed")
            st.error(str(error))
    output = st.session_state.get("labels_output")
    if output and output["signature"] == signature:
        st.success("Sample labels generated and saved. Check product names, IFB number and print scale before printing.")
        if output["warning"]:
            st.warning("Word labels were saved, but PDF conversion failed: " + output["warning"])
        download_files(output["files"], "sample_labels")
