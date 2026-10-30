"""Statement of Compliance screen, independent of tender letter generation."""
from datetime import date
import hashlib
import json
import logging
import uuid

import streamlit as st

import documents
from statement_compliance import (DEFAULTS, FIELDS, regenerate_statement, statement_payload,
                                  template_bytes, validate_statement)


def render_statement_compliance(store, cloud_mode, download_files):
    st.subheader("Statement of Compliance")
    st.caption("Fill the SPMC required/offered material form for one item. Download an editable Word document and a PDF copy, or regenerate a previous statement from Saved runs.")
    for field, default in DEFAULTS.items():
        st.session_state.setdefault("compliance_" + field, date.fromisoformat(default) if field.endswith("_valid_until") else default)

    with st.expander("Load an item or foreign bidder (optional)"):
        tenders = store.tenders()
        reference = st.selectbox("Tender catalogue", [None] + list(tenders),
            format_func=lambda value: value or "Enter item manually", key="compliance_reference")
        if reference:
            catalogue = {item["item_number"]: item for item in store.catalog(reference)}
            number = st.selectbox("Catalogue item", [None] + list(catalogue),
                format_func=lambda value: "Select an item" if value is None else f"{value} - {catalogue[value]['description']}",
                key=f"compliance_catalogue_{reference}")
            if st.button("Load item details", disabled=number is None, key="compliance_load_item"):
                item = catalogue[number]
                st.session_state["compliance_item_number"] = number
                st.session_state["compliance_item_name"] = item["description"]
                st.session_state["compliance_offered_item"] = item["description"]
                quantity = (item.get("quantity_kg", "") + " kg").strip() if item.get("quantity_kg") else ""
                st.session_state["compliance_required_quantity"] = quantity
                st.session_state["compliance_offered_quantity"] = quantity
                st.session_state.pop("compliance_output", None)
        suppliers = store.suppliers()
        supplier_id = st.selectbox("Foreign bidder profile", [None] + list(suppliers),
            format_func=lambda value: "Enter bidder manually" if value is None else suppliers[value]["supplier_name"], key="compliance_supplier")
        if st.button("Load bidder details", disabled=supplier_id is None, key="compliance_load_bidder"):
            supplier = suppliers[supplier_id]
            st.session_state["compliance_bidder"] = "\n".join(filter(None, [supplier["supplier_name"], supplier.get("supplier_address", "")]))
            for suffix in ("phone", "fax", "email"):
                st.session_state["compliance_bidder_" + suffix] = supplier.get("supplier_" + suffix, "")
            st.session_state.pop("compliance_output", None)
        st.caption("Loaded values remain editable. Check the offered specification and quantity against your actual offer.")

    values = {}

    def field(key, multiline=False):
        widget = st.text_area if multiline else st.text_input
        values[key] = widget(FIELDS[key], key="compliance_" + key)

    left, right = st.columns(2)
    with left:
        field("item_number")
        field("item_name", True)
        field("required_quantity")
    with right:
        field("offered_item", True)
        field("offered_quantity")
    st.markdown("**Delivery, packaging and price**")
    left, right = st.columns(2)
    with left:
        for key in ("delivery_schedule", "packaging", "payment", "transport"):
            field(key, key != "payment")
    with right:
        for key in ("price_per_kg", "commission", "total_cost", "total_words"):
            field(key, key == "total_words")
        st.caption("Enter the quoted total and words explicitly, including currency. Prices and commissions are not added or converted automatically.")
    st.markdown("**Validity and supporting details**")
    st.caption("Starting dates come from the supplied blank form: offer 1 February 2027 and bid security 1 March 2027. Check them for each tender; the form retains the stated 91 / 119 day requirements.")
    left, right = st.columns(2)
    with left:
        field("shelf_life")
        field("origin")
        values["offer_valid_until"] = str(st.date_input("Required offer validity up to", key="compliance_offer_valid_until"))
        field("offer_response")
    with right:
        field("sample")
        field("coa", True)
        values["security_valid_until"] = str(st.date_input("Required bid security validity up to", key="compliance_security_valid_until"))
        field("security", True)
    st.markdown("**Manufacturer, foreign bidder and local agent**")
    for column, party in zip(st.columns(3), ("manufacturer", "bidder", "agent")):
        with column:
            field(party, True)
            for suffix in ("phone", "fax", "email"):
                field(party + "_" + suffix)
    st.caption("20. The signature and official seal area is left blank for signing after printing. Enter N/A explicitly for responses that do not apply.")
    valid = False
    try:
        cleaned = validate_statement(values)
        valid = True
        blank = [label.split(". ")[0] for key, label in FIELDS.items()
                 if label[0].isdigit() and not cleaned[key]]
        if blank:
            st.info("Responses still blank: " + ", ".join(blank) + ". You can download a draft and complete these in Word.")
    except ValueError as error:
        if values["item_name"]:
            st.warning(str(error))
    pdf_ready = bool(documents.pdf_available())
    with_pdf = st.checkbox("Include PDF copy", value=pdf_ready, disabled=not pdf_ready, key="compliance_pdf")
    if not pdf_ready:
        st.caption("Word download is available. Install LibreOffice to enable PDF copies.")
    signature = hashlib.sha256(json.dumps([values, with_pdf], sort_keys=True).encode()).hexdigest()
    if st.button("Generate Statement of Compliance", type="primary", disabled=not valid, key="compliance_generate"):
        st.session_state.pop("compliance_output", None)
        try:
            with st.spinner("Preparing Statement of Compliance…"):
                payload = statement_payload(values, with_pdf)
                files = regenerate_statement(payload)
                warning = ""
                if with_pdf:
                    try:
                        files.update(documents.convert_pdfs(files))
                    except Exception as error:
                        logging.exception("Statement of Compliance PDF conversion failed")
                        warning = str(error)
                folder = ""
                if not cloud_mode:
                    destination = store.root / "exports" / ("compliance_" + uuid.uuid4().hex[:8])
                    destination.mkdir(parents=True)
                    for name, content in files.items():
                        (destination / name).write_bytes(content)
                    folder = str(destination)
                    payload["output_directory"] = folder
                store.save_record("Statement of Compliance · " + (values["item_number"] + " " + values["item_name"]).strip(), payload)
                st.session_state["compliance_output"] = {"signature": signature, "files": files, "warning": warning, "folder": folder}
        except Exception as error:
            logging.exception("Statement of Compliance generation failed")
            st.error(str(error))
    output = st.session_state.get("compliance_output")
    if output and output["signature"] == signature:
        st.success("Statement generated and details saved. Review all responses and dates before signing.")
        if output["warning"]:
            st.warning("Word document was saved, but PDF conversion failed: " + output["warning"])
        if output["folder"]:
            st.caption("Saved to: " + output["folder"])
        download_files(output["files"], "statement_compliance")
    with st.expander("Editable form template"):
        st.download_button("Download Word template", template_bytes(), file_name="Statement of Compliance template.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key="compliance_download_template")
