"""Run with: streamlit run app.py"""
import json
from datetime import date

import streamlit as st

from documents import (FIELDS, Store, build_context, convert_pdf, create_starters,
                       filename, make_zip, normalize_word, pdf_available,
                       render_document, template_variables)

st.set_page_config(page_title="USECTA Documents", page_icon="📄", layout="wide")
store = Store()
create_starters(store)


def load_fields(fields, items=None, project=None, selected=None):
    for key, value in fields.items():
        st.session_state[f"field_{key}"] = value
    if items is not None:
        st.session_state["item_rows"] = items
        st.session_state["editor_version"] = st.session_state.get("editor_version", 0) + 1
    if project is not None:
        st.session_state["project_name"] = project
    if selected is not None:
        st.session_state["selected_templates"] = selected
    st.session_state.pop("generated", None)


st.title("Company documents, ready in minutes")
st.caption("Enter details once. Generate consistent letters and bids using your Word templates. No AI APIs required.")
with st.sidebar:
    st.header("Your workspace")
    st.caption("Profiles, projects, and templates are stored on this computer in the data folder.")
    profiles = store.profiles()
    selected_profile = st.selectbox("Saved company / personnel profiles", ["Choose a profile"] + list(profiles))
    if st.button("Load profile", disabled=selected_profile not in profiles):
        load_fields(profiles[selected_profile])
        st.success("Profile loaded.")
    records = store.records()
    record_map = {r["id"]: r for r in records}
    record_id = st.selectbox("Saved projects", [None] + list(record_map), format_func=lambda key: "Choose a project" if key is None else f"{record_map[key]['name']} · {record_map[key]['created_at'][:10]}")
    if st.button("Load project", disabled=record_id is None):
        record = record_map[record_id]
        payload = json.loads(record["payload"])
        load_fields(payload["fields"], payload["items"], record["name"], payload.get("templates"))
        st.success("Project loaded.")
    st.divider()
    st.caption("Starter wording is illustrative. Replace it with your company’s approved documents before use.")

generate_tab, templates_tab = st.tabs(["Create documents", "Template library"])
with generate_tab:
    templates = store.templates()
    by_id = {t["id"]: t for t in templates}
    selected = st.multiselect("Documents to create", list(by_id), default=[t["id"] for t in templates if t["id"].startswith("starter-")], format_func=lambda key: by_id[key]["name"] + " · " + key[:8], key="selected_templates")
    used = set()
    required = set()
    for key in selected:
        used.update(template_variables(store.template_path(by_id[key]).read_bytes()))
        required.update(by_id[key]["required"])
    st.caption("Fields marked * are required by your selected templates.")
    st.text_input("Project name (for saved records)", key="project_name", placeholder="Example: Office equipment bid — October")
    fields = {}
    sections = [
        ("Company", ["company_name", "company_address", "company_email", "company_phone"]),
        ("Recipient & document", ["customer_name", "customer_address", "document_date", "bid_reference", "currency"]),
        ("Personnel & signatures", ["authorized_person_name", "authorized_person_designation", "authorized_person_id", "signatory_name", "signatory_designation"]),
        ("Agreement & delivery", ["agreement_subject", "agreement_terms", "delivery_terms"]),
    ]
    for title, keys in sections:
        with st.expander(title, expanded=title in ["Company", "Recipient & document"]):
            left, right = st.columns(2)
            for index, key in enumerate(keys):
                defaults = {"document_date": date.today().isoformat(), "currency": "LKR"}
                st.session_state.setdefault(f"field_{key}", defaults.get(key, ""))
                label = FIELDS[key] + (" *" if key in required else "")
                with (left if index % 2 == 0 else right):
                    if key.endswith("address") or key in ["agreement_terms", "delivery_terms"]:
                        fields[key] = st.text_area(label, key=f"field_{key}")
                    else:
                        fields[key] = st.text_input(label, key=f"field_{key}")
    extra = sorted(used - set(FIELDS) - {"items", "grand_total"})
    if extra:
        st.subheader("Additional template fields")
        for key in extra:
            fields[key] = st.text_input(key.replace("_", " ").title() + (" *" if key in required else ""), key=f"field_{key}")
    st.subheader("Item list")
    st.caption("Add or remove rows. Prices use two decimal places; totals are calculated automatically. No tax is added automatically.")
    st.session_state.setdefault("item_rows", [{"description": "", "quantity": 0.0, "unit_price": 0.0}])
    rows = st.data_editor(st.session_state["item_rows"], num_rows="dynamic", hide_index=True, width="stretch",
        key=f"items_{st.session_state.get('editor_version', 0)}", column_config={
            "description": st.column_config.TextColumn("Description"),
            "quantity": st.column_config.NumberColumn("Quantity", min_value=0, step=1.0),
            "unit_price": st.column_config.NumberColumn("Unit price", min_value=0, step=0.01, format="%.2f"),
        })
    context = None
    try:
        context = build_context(fields, rows)
        st.metric(f"Grand total ({fields['currency']})", context["grand_total"])
    except ValueError as exc:
        st.warning(str(exc))
    with st.expander("Save details for next time"):
        profile_name = st.text_input("Profile name", placeholder="Company / person name")
        pcol, rcol = st.columns(2)
        if pcol.button("Save company & personnel profile"):
            try:
                keys = sections[0][1] + sections[2][1]
                store.save_profile(profile_name, {key: fields[key] for key in keys})
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        if rcol.button("Save project"):
            try:
                if context is None:
                    raise ValueError("Correct the item list before saving.")
                store.save_record(st.session_state["project_name"], {"fields": fields, "items": rows, "templates": selected})
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    can_pdf = bool(pdf_available())
    with_pdf = st.checkbox("Include PDF copies", disabled=not can_pdf)
    if not can_pdf:
        st.info("DOCX export is available. Install LibreOffice to enable PDF copies, or export your downloads to PDF in Word.")
    # Downloads are bound to their inputs so changed forms cannot expose stale results.
    fingerprint = json.dumps({"fields": fields, "rows": rows, "selected": selected, "pdf": with_pdf}, sort_keys=True)
    if st.button("Generate documents", type="primary", disabled=not selected or context is None):
        files = {}
        try:
            with st.spinner("Preparing your documents…"):
                for key in selected:
                    template = by_id[key]
                    content = render_document(store.template_path(template).read_bytes(), context, template["required"])
                    stem = filename(template["name"]) + "_" + key[:8]
                    files[stem + ".docx"] = content
                    if with_pdf:
                        files[stem + ".pdf"] = convert_pdf(content)
            st.session_state["generated"] = {"fingerprint": fingerprint, "files": files}
        except Exception as exc:
            st.session_state.pop("generated", None)
            st.error(f"Could not generate documents: {exc}")
    result = st.session_state.get("generated")
    if result and result["fingerprint"] == fingerprint:
        st.success("Documents generated. Review names, wording, totals, and layout before signing or sending.")
        for name, content in result["files"].items():
            st.download_button(f"Download {name}", content, file_name=name,
                mime="application/pdf" if name.endswith(".pdf") else "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        st.download_button("Download all as ZIP", make_zip(result["files"]), file_name="company_documents.zip", mime="application/zip")

with templates_tab:
    st.subheader("Your Word templates")
    st.write("Use a DOCX or DOTX sample. Replace changing text with placeholders such as `{{ company_name }}` and upload it here. A PDF sample must first be recreated in Word.")
    st.caption("Each upload is stored as a separate version. Existing templates and records are preserved.")
    with st.expander("Available placeholders and repeating tables"):
        st.code("\n".join("{{ " + key + " }} — " + label for key, label in FIELDS.items()))
        st.write("Custom placeholders such as `{{ purchase_order_number }}` automatically create additional fields. Use plain field names. For conditional wording, use `{% if delivery_terms %}...{% endif %}`.")
        st.write("For an item table, create a header row, then three separate rows: a loop-start row, an item row, and a loop-end row. Put each loop tag in the first cell of its own row. The two tag rows disappear on generation.")
        st.code("{%tr for item in items %}\n{{ item.number }} | {{ item.description }} | {{ item.quantity }} | {{ item.unit_price }} | {{ item.total }}\n{%tr endfor %}\nGrand total: {{ currency }} {{ grand_total }}")
        st.caption("Download the starter bid template below for a working table example. Keep each placeholder together when formatting it in Word.")
    upload = st.file_uploader("Upload a Word template", type=["docx", "dotx"])
    if upload:
        try:
            content = normalize_word(upload.getvalue())
            variables = sorted(template_variables(content))
            st.write("Detected fields: " + (", ".join(variables) or "No placeholders found"))
            name = st.text_input("Template name", value=upload.name.rsplit(".", 1)[0])
            required_upload = st.multiselect("Required fields", variables, default=variables)
            if st.button("Add template version", disabled=not variables):
                store.add_template(name, content, required_upload)
                st.rerun()
        except Exception as exc:
            st.error(f"Check your template: {exc}")
    for template in store.templates():
        with st.expander(f"{template['name']} · {template['created_at'][:10]} · {template['id'][:8]}"):
            st.caption("Required: " + ", ".join(template["required"]))
            st.download_button("Download editable template", store.template_path(template).read_bytes(),
                file_name=filename(template["name"]) + "_template.docx", key=f"template_{template['id']}")
