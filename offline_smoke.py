"""End-to-end smoke check shipped inside the frozen application."""
import json
import socket
import tempfile
import time
from datetime import date
from pathlib import Path


def run_smoke(report_root):
    from documents import Store, pdf_available, convert_pdfs
    from workflows import prepare_workspace, choose_items, tender_context, tender_jobs, generate_files, quotation_context, quotation_jobs
    from workspace_archive import export_workspace, restore_workspace, import_company_records
    timings = {}
    with tempfile.TemporaryDirectory(prefix="usecta-offline-smoke-") as temp:
        root = Path(temp)
        store = Store(root / "source")
        start = time.perf_counter()
        prepare_workspace(store)
        timings["initialization_seconds"] = round(time.perf_counter() - start, 3)
        assert len(store.templates()) == 7
        assert len(store.catalog("SPMC/03/2026")) == 50
        supplier = {"supplier_name": "SAMPLE ONLY Supplier", "supplier_country": "Example Country", "supplier_address": "Sample Address", "supplier_registration_number": "SAMPLE-123"}
        store.save_supplier(supplier)
        tender = store.tenders()["SPMC/03/2026"] | {"bid_valid_until": "2027-02-03"}
        rows = choose_items(store, "SPMC/03/2026", ["2", "15", "34"])
        context = tender_context("SPMC/03/2026", tender, rows, supplier, date(2026, 10, 10), date(2026, 10, 10))
        ids = [t["id"] for t in store.templates() if t["workflow"] == "tender"]
        jobs = tender_jobs(store, ids, context)
        start = time.perf_counter()
        files = generate_files(store, jobs)
        timings["ten_tender_docx_seconds"] = round(time.perf_counter() - start, 3)
        assert len(files) == 10
        samples = report_root / "samples"
        samples.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            (samples / name).write_bytes(content)
        qcontext = quotation_context({"quotation_number": "SAMPLE-QT", "customer_name": "Sample Customer", "customer_address": "", "currency": "USD", "document_date": "10 October 2026", "quotation_expiry_date": "17 October 2026", "shipment_mode": "", "container_details": "", "shipment_quantity": "", "packaging_details": "", "payment_terms": "", "quotation_notes": ""}, [{"description": "Sample Product", "quantity": 2, "unit": "kg", "unit_price": 100}])
        quote_ids = [t["id"] for t in store.templates() if t["workflow"] == "quotation"]
        assert len(generate_files(store, quotation_jobs(store, quote_ids, qcontext))) == 1
        from sample_labels import label_files
        label_docs = label_files("SAMPLE-IFB", ["Sample Product A", "Sample Product B", "Sample Product C"])
        for name, content in label_docs.items():
            (samples / name).write_bytes(content)
        store.save_record("Sample smoke run", {"jobs": jobs, "with_pdf": False})
        backup = export_workspace(store)
        restored = Store(root / "restored")
        restore_workspace(restored, backup)
        assert len(restored.records()) == 1
        assert generate_files(restored, json.loads(restored.records()[0]["payload"])["jobs"]) == files
        shared = Store(root / "shared")
        import_company_records(shared, export_workspace(store, shared=True))
        assert len(shared.suppliers()) == 1 and not shared.records()
        pdf_status = "unavailable"
        if pdf_available():
            start = time.perf_counter()
            pdfs = convert_pdfs(files)
            timings["ten_tender_pdf_seconds"] = round(time.perf_counter() - start, 3)
            assert len(pdfs) == 10 and all(data.startswith(b"%PDF-") for data in pdfs.values())
            for name, content in pdfs.items():
                (samples / name).write_bytes(content)
            pdf_status = "passed"
            label_pdfs = convert_pdfs(label_docs)
            assert len(label_pdfs) == 1 and all(data.startswith(b"%PDF-") for data in label_pdfs.values())
            for name, content in label_pdfs.items():
                (samples / name).write_bytes(content)
        try:
            socket.create_connection(("example.com", 443), timeout=1)
        except OSError:
            network_status = "external connection blocked"
        else:
            raise AssertionError("External connection was not blocked")
        report = {"status": "passed", "network": network_status, "pdf": pdf_status, "templates": 7, "catalogue_items": 50, "docx_files": 11, "sample_labels_docx": "passed", "sample_labels_pdf": "passed" if pdf_status == "passed" else "unavailable", "backup_restore": "passed", "company_import": "passed", "timings": timings}
        report_root.mkdir(parents=True, exist_ok=True)
        (report_root / "offline-smoke.json").write_text(json.dumps(report, indent=2))
