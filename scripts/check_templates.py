"""Validate copies of the user's templates with explicitly fictitious sample data.

Usage: python scripts/check_templates.py data/review/templates --pdf
Never modifies the input files or saves a fictitious tender in the application DB.
"""
import argparse
import io
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lxml import etree

from documents import Store, convert_pdf, render_document, template_variables
from workflows import import_catalog, tender_context, tender_jobs

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def signature(element):
    return (element.tag, tuple(sorted(element.attrib.items())), tuple(signature(child) for child in element))


def check_layout(before, after):
    with zipfile.ZipFile(io.BytesIO(before)) as src, zipfile.ZipFile(io.BytesIO(after)) as dst:
        protected = [name for name in src.namelist() if name.startswith(("word/media/", "word/theme/")) or name in {"word/styles.xml", "word/numbering.xml", "word/settings.xml"}]
        assert all(src.read(name) == dst.read(name) for name in protected), "An unrelated style, media, or settings part changed"
        a = etree.fromstring(src.read("word/document.xml"))
        b = etree.fromstring(dst.read("word/document.xml"))
        for tag in ["sectPr", "tblPr", "tblGrid"]:
            assert [signature(x) for x in a.findall(f".//w:{tag}", NS)] == [signature(x) for x in b.findall(f".//w:{tag}", NS)], f"Layout property {tag} changed"
        text = "".join(b.xpath("//w:t/text()", namespaces=NS))
        assert "{{" not in text and "{%" not in text, "Unfilled placeholder found"
        # Validate the repeated collection rows retain the source cell widths,
        # alignment, and row properties rather than being reconstructed.
        for source_table, output_table in zip(a.findall(".//w:tbl", NS), b.findall(".//w:tbl", NS)):
            data_row = next((r for r in source_table.findall("w:tr", NS) if "item.item_number" in "".join(r.xpath(".//w:t/text()", namespaces=NS))), None)
            if data_row is not None:
                cells = data_row.findall("w:tc", NS)
                expected = [[signature(x) for x in cell.findall("w:tcPr", NS)] for cell in cells]
                for row in output_table.findall("w:tr", NS)[1:]:
                    assert [[signature(x) for x in cell.findall("w:tcPr", NS)] for cell in row.findall("w:tc", NS)] == expected, "Repeated cell properties changed"
    return {"protected_parts": len(protected), "section_and_table_properties": "preserved"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/review/sample_output"))
    parser.add_argument("--pdf", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    # A dedicated temporary database contains only test templates.
    import tempfile
    with tempfile.TemporaryDirectory(prefix="usecta-template-check-") as temp:
        store = Store(Path(temp))
        originals = {}
        for path in sorted(args.folder.glob("*.docx")):
            content = path.read_bytes()
            variables = template_variables(content)
            scope = "item" if {"item_number", "item_description"} & variables else "supplier" if "agreement_item_names" in variables else "batch" if "tender_items" in variables else "tender"
            key = store.add_template(path.stem, content, sorted(variables), workflow="tender", scope=scope)
            originals[key] = content
        if not originals:
            raise ValueError("No DOCX templates found.")
        rows = import_catalog((Path(__file__).resolve().parents[1] / "catalogues/SPMC_03_2026.csv").read_bytes(), ".csv")
        sample = tender_context("SAMPLE/TEST/2026", {"closing_date": "2026-11-20", "closing_time": "14:30", "bid_valid_until": "2027-02-20", "tender_title": "PROCUREMENT OF PHARMACEUTICAL RAW MATERIALS"}, [rows[1], rows[14], rows[33]], {"supplier_name": "Example Chemicals Ltd", "supplier_country": "China", "supplier_registration_number": "TEST-123", "supplier_address": "100 Example Road, Example City"}, "2026-11-01", "2026-11-02")
        jobs = tender_jobs(store, list(originals), sample)
        # Stress the list documents with the complete catalogue, without
        # unnecessarily producing 100 individual bid forms and cover letters.
        full = tender_context("SAMPLE/TEST/2026", {"closing_date": "2026-11-20", "closing_time": "14:30", "bid_valid_until": "2027-02-20", "tender_title": "PROCUREMENT OF PHARMACEUTICAL RAW MATERIALS"}, rows, sample, "2026-11-01", "2026-11-02")
        list_ids = [t["id"] for t in store.templates() if t["scope"] == "batch"]
        for job in tender_jobs(store, list_ids, full):
            job["filename"] += "_50_items"
            jobs.append(job)
        report = {"sample_data_only": True, "actual_tender_dates": "not supplied", "documents": []}
        for job in jobs:
            template = next(t for t in store.templates() if t["id"] == job["template_id"])
            word = render_document(originals[template["id"]], job["context"], template["required"])
            layout = check_layout(originals[template["id"]], word)
            name = "SAMPLE_ONLY_" + job["filename"]
            (args.output / (name + ".docx")).write_bytes(word)
            result = {"template": template["name"], "filename": name, "layout": layout}
            if args.pdf:
                pdf = convert_pdf(word)
                (args.output / (name + ".pdf")).write_bytes(pdf)
                result["pdf"] = "converted"
            report["documents"].append(result)
        (args.output / "validation_report.json").write_text(json.dumps(report, indent=2))
        print(f"Validated {len(jobs)} sample documents; original style, image, section, and table settings preserved.")
        print(f"Sample outputs and validation report: {args.output}")


if __name__ == "__main__":
    main()
