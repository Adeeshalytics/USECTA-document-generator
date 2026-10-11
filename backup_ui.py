"""Offline workspace management; loaded only when the user opens this screen."""
import os
from datetime import date

import streamlit as st
from desktop_paths import offline_mode
from workspace_archive import (export_workspace, inspect_archive, archive_summary,
                               restore_workspace, import_company_records)


def render_backup_screen(store):
    st.subheader("Backup & sharing")
    st.caption("Workspace: " + str(store.root))
    if offline_mode() and st.button("Open workspace folder"):
        os.startfile(store.root)
    st.write("Each computer keeps its own records. Use a company package to share suppliers, tenders, catalogues and templates. Saved runs remain private to your workspace.")
    kind = st.radio("Create package", ["Complete workspace backup", "Company records to share"], key="archive_kind")
    shared = kind == "Company records to share"
    st.caption("Backups include records and template versions. Generated output files can be regenerated from saved runs; they are not duplicated in the backup.")
    if st.button("Prepare package"):
        try:
            st.session_state["_archive_download"] = {"kind": kind, "content": export_workspace(store, shared)}
        except (ValueError, OSError) as exc:
            st.error(str(exc))
    prepared = st.session_state.get("_archive_download", {})
    if prepared.get("kind") == kind:
        st.download_button("Download package", prepared["content"], file_name=f"USECTA_{'share' if shared else 'backup'}_{date.today()}.zip", mime="application/zip")
    st.divider()
    st.subheader("Import or restore")
    upload = st.file_uploader("USECTA backup or company package", type=["zip"], key="archive_upload")
    if upload:
        try:
            payload, _ = inspect_archive(upload.getvalue())
            st.json(archive_summary(payload))
            if payload["kind"] == "backup":
                st.warning("Restore replaces suppliers, tenders, templates and history in this workspace. A safety backup is saved locally first.")
                confirmed = st.checkbox("Replace this workspace with the reviewed backup", key="restore_confirm")
                if st.button("Restore workspace", disabled=not confirmed, type="primary"):
                    safety = restore_workspace(store, upload.getvalue())
                    st.session_state.clear()
                    st.session_state["_restore_message"] = "Workspace restored. Previous workspace backup: " + str(safety)
                    st.rerun()
            else:
                existing_tenders, existing_suppliers = store.tenders(), store.suppliers()
                names = {s["supplier_name"].casefold() for s in existing_suppliers.values()}
                conflicts = ["Tender: " + ref for ref in payload["tenders"] if ref in existing_tenders]
                conflicts += ["Supplier: " + s["supplier_name"] for key, s in payload["suppliers"].items() if key in existing_suppliers or s["supplier_name"].casefold() in names]
                if conflicts:
                    st.write("Existing records in this package:")
                    st.write(conflicts)
                replace = st.checkbox("Replace conflicting supplier and tender details (otherwise keep existing)", key="import_replace")
                st.caption("Templates import as separate versions. Saved document runs are never replaced. A safety backup is created first.")
                if st.button("Import company records", type="primary"):
                    counts = import_company_records(store, upload.getvalue(), replace)
                    st.session_state.pop("_archive_download", None)
                    st.success("Imported: " + ", ".join(f"{n} {name}" for name, n in counts.items()))
        except (ValueError, OSError) as exc:
            st.error(str(exc))
    if st.session_state.get("_restore_message"):
        st.success(st.session_state.pop("_restore_message"))
