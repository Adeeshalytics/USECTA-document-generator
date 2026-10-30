"""Recreate the supplied two-page SPMC compliance form as an editable template."""
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ROW_HEIGHT_RULE, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]


def create_template():
    doc = Document()
    doc.core_properties.title = "Statement of Compliance"
    doc.core_properties.author = "USECTA (Pvt) Ltd"
    style = doc.styles["Normal"]
    style.font.name, style.font.size = "Times New Roman", Pt(11)
    style.font.color.rgb = RGBColor(0, 0, 0)
    style.paragraph_format.space_after = Pt(0)
    style.paragraph_format.line_spacing = 1
    for document_style in doc.styles:
        for border in document_style.element.findall(".//" + qn("w:pBdr")):
            border.getparent().remove(border)
    section = doc.sections[0]
    section.page_width, section.page_height = Pt(596.52), Pt(842.52)
    section.left_margin, section.right_margin = Pt(66), Pt(32)
    section.top_margin, section.bottom_margin = Pt(64), Pt(40)
    section.footer_distance = Pt(18)
    heading = doc.add_paragraph("3.   STATEMENT OF COMPLIANCE", "Title")
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    heading.paragraph_format.space_after = Pt(14)
    heading.paragraph_format.line_spacing = 1
    for border in heading._p.findall(".//" + qn("w:pBdr")):
        border.getparent().remove(border)
    for run in heading.runs:
        run.font.name, run.font.size, run.bold = "Times New Roman", Pt(12), True
        run.font.color.rgb = RGBColor(0, 0, 0)
    p = doc.add_paragraph("SUPPLY OF {{ supply_item }}")
    p.paragraph_format.space_after = Pt(12)
    instructions = [
        "i)     Duly filled statement of compliance should be sent with the Bid document.",
        "ii)    Specify whether offered specifications comply with required specifications.",
        "iii)   Bid may be considered as invalid if this statement of compliance is not duly filled.",
        "iv)   Bidders are instructed to send a covering letter in their company letter head with the official seal with the duly filled statement of compliance",
    ]
    for text in instructions:
        doc.add_paragraph(text)
    doc.paragraphs[-1].paragraph_format.space_after = Pt(10)

    def table():
        result = doc.add_table(rows=0, cols=3)
        result.autofit = False
        result.alignment = WD_TABLE_ALIGNMENT.LEFT
        for col, width in zip(result.columns, [27, 241, 230]):
            col.width = Pt(width)
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            el = OxmlElement("w:" + edge)
            for name, value in [("val", "single"), ("sz", "4"), ("color", "777777")]:
                el.set(qn("w:" + name), value)
            borders.append(el)
        result._tbl.tblPr.append(borders)
        return result

    def row(table, number, required, offered, height, header=False):
        r = table.add_row()
        r.height, r.height_rule = Pt(height), WD_ROW_HEIGHT_RULE.AT_LEAST
        r._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        if header:
            r._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
        for i, (cell, text, width) in enumerate(zip(r.cells, [number, required, offered], [27, 241, 230])):
            cell.width = Pt(width)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            margins = OxmlElement("w:tcMar")
            for edge, value in [("top", 25), ("bottom", 25), ("left", 85), ("right", 85)]:
                el = OxmlElement("w:" + edge)
                el.set(qn("w:w"), str(value)); el.set(qn("w:type"), "dxa")
                margins.append(el)
            cell._tc.get_or_add_tcPr().append(margins)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run(text).bold = header
        return r

    def header(t):
        row(t, "", "Description and Specification of\nREQUIRED Material", "Description and Specification of\nOFFERED Material", 36, True)

    t = table(); header(t)
    rows = [
        ("1.", "Item:\n(As Per the Schedule of requirement)\n{{ item_name }}", "offered_item", 55),
        ("2.", "Quantity\n(As Per the Schedule of requirement)\n{{ required_quantity }}", "offered_quantity", 32),
        ("3.", "Delivery schedule\n\n(As Per the Schedule of requirement)", "delivery_schedule", 42),
        ("4.", "Packaging\n\n(As Per the Schedule of requirement)", "packaging", 56),
        ("5.", "Mode of payment", "payment", 27),
        ("6.", "Mode of transport (Sea/Air)\nPort of Shipment", "transport", 32),
        ("7.", "C&F price per kg\n(Should quote only C&F price)", "price_per_kg", 35),
        ("8.", "Local Agent's commission", "commission", 21),
        ("9.", "Total cost", "total_cost", 21),
        ("10.", "Total Cost in Words", "total_words", 26),
        ("11.", "Shelf life\nAs requested in the schedule of requirement", "shelf_life", 32),
        ("12.", "Country of origin", "origin", 21),
        ("13.", "Validity of Offer\nUp to {{ offer_valid_until }}\n(91 days from the date of closing)", "offer_response", 50),
        ("14.", "State whether sample is included or not", "sample", 35),
    ]
    for num, required, field, height in rows:
        row(t, num, required, "{{ " + field + " }}", height)
    # A separate section preserves the near-top continuation table in the source.
    continuation = doc.add_section(WD_SECTION_START.NEW_PAGE)
    continuation.top_margin = Pt(16)
    t = table(); header(t)
    row(t, "15.", "Certificate of analysis must include above specifications.", "{{ coa }}", 72)
    for num, field, label in [("16.", "manufacturer", "Name & address of the manufacturer of the material"),
                              ("17.", "bidder", "Name & address of the Bidder (foreign)"),
                              ("18.", "agent", "Name & address of the local agent\n(If applicable)")]:
        row(t, num, label, "{{ " + field + " }}", 76)
        for suffix, contact in [("phone", "Telephone:"), ("fax", "Fax:"), ("email", "e-mail:")]:
            row(t, "", contact, "{{ " + field + "_" + suffix + " }}", 23)
    row(t, "19.", "Bid security submitted/not submitted & value\nUp to {{ security_valid_until }}\n(119 days from the date of closing)", "{{ security }}", 48)
    row(t, "20.", "Signature and official seal of the Bidder", "", 84)
    # The source uses bid-pack page labels 44 and 45; use actual page fields.
    for sec in doc.sections:
        p = sec.footer.paragraphs[0]
        if not p.text and not p._p.xpath(".//w:fldSimple"):
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            fld = OxmlElement("w:fldSimple"); fld.set(qn("w:instr"), "PAGE")
            p._p.append(fld)
    path = ROOT / "assets" / "Statement of Compliance.docx"
    doc.save(path)
    print(path)


if __name__ == "__main__":
    create_template()
