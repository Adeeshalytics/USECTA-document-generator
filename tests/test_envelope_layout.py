"""Four envelope labels and automatic selection of the revised built-in."""
import io
from pathlib import Path

import pytest
from docx import Document
from docx.enum.table import WD_ROW_HEIGHT_RULE
from docx.oxml.ns import qn

from documents import Store, render_document, template_variables
from workflows import current_tender_templates, prepare_workspace

ROOT = Path(__file__).resolve().parents[1]
OLD_KEY = "usecta-2277f22d37028e6836f2"


def test_four_envelope_boxes_preserve_all_fields_on_a4():
    source = (ROOT / "company_templates/Envelop covers.docx").read_bytes()
    assert template_variables(source) == {"bid_reference", "tender_title", "closing_date_short", "closing_time"}
    doc = Document(io.BytesIO(render_document(source, {
        "bid_reference": "SPMC/03/2026", "tender_title": "RAW MATERIALS <A> & B",
        "closing_date_short": "03.11.2026", "closing_time": "12.45 p.m.",
    })))
    assert doc.sections[0].page_width.mm == pytest.approx(210, abs=0.02)
    assert doc.sections[0].page_height.mm == pytest.approx(297, abs=0.02)
    table, = doc.tables
    boxes = [table.cell(row, col) for row, col in ((0, 0), (0, 2), (2, 0), (2, 2))]
    assert "ORIGINAL BID" in boxes[0].text and "COPY OF BID" in boxes[1].text
    assert "IFB Number:" in boxes[2].text and "Closing Date:" in boxes[2].text
    for cell in (boxes[0], boxes[1], boxes[3]):
        assert "Chairman Procurement Committee" in cell.text
        assert "33/5 Boruppa Road" in cell.text
        assert "12.45 p.m." in cell.text and "DO NOT OPEN BEFORE" in cell.text
    assert all("SPMC/03/2026" in cell.text for cell in boxes[:3])
    assert all("RAW MATERIALS <A> & B" in cell.text for cell in boxes[:2])
    for row in table.rows:
        assert row.height_rule == WD_ROW_HEIGHT_RULE.AT_LEAST
        assert row._tr.find(qn("w:trPr")).find(qn("w:cantSplit")) is not None
    assert sum(row.height.mm for row in table.rows) < 297 - 24 - 10
    assert len(boxes) == sum(
        cell._tc.get_or_add_tcPr().find(qn("w:tcBorders")).find(qn("w:top")).get(qn("w:val")) == "single"
        for row in table.rows for cell in row.cells)


def test_upgrade_offers_new_envelope_and_preserves_prior_templates(tmp_path):
    store = Store(tmp_path)
    doc = Document()
    doc.add_paragraph("Previous envelope {{ bid_reference }}")
    stream = io.BytesIO()
    doc.save(stream)
    old = stream.getvalue()
    store.add_template("Envelop covers", old, key=OLD_KEY, workflow="tender", scope="tender")
    custom = store.add_template("My envelope", old, workflow="tender", scope="tender")
    assert OLD_KEY in {t["id"] for t in current_tender_templates(store)}
    prepare_workspace(store)
    active = current_tender_templates(store)
    envelope, = [t for t in active if t["name"] == "Envelop covers"]
    assert envelope["id"] != OLD_KEY and custom in {t["id"] for t in active}
    previous = next(t for t in store.templates() if t["id"] == OLD_KEY)
    assert store.template_path(previous).read_bytes() == old
    prepare_workspace(store)
    assert current_tender_templates(store) == active
