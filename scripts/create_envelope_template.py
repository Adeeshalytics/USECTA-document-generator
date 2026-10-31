"""Arrange the four existing envelope labels on a single A4 sheet."""
import io
from pathlib import Path
import zipfile

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "company_templates/Envelop covers.docx"
RECIPIENT = ("Chairman Procurement Committee\nState Pharmaceuticals Manufacturing Corporation\n"
             "No.11, Sir John Kotelawala Mw,\nKandawala Estate, Ratmalana, Sri Lanka")
SENDER = "USECTA PVT LTD\n33/5 Boruppa Road, Pallegunnepana,\nGunnepana, Kandy"


def paragraph(cell, text, size=11, bold=False, after=5):
    p = cell.paragraphs[0] if not cell.paragraphs[0].text else cell.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fmt = p.paragraph_format
    fmt.space_before, fmt.space_after = Pt(0), Pt(after)
    fmt.line_spacing = 1
    fmt.keep_together = True
    fmt.keep_with_next = False
    run = p.add_run(text)
    run.font.name, run.font.size, run.bold = "Calibri", Pt(size), bold
    run.font.color.rgb = RGBColor(0, 0, 0)


def create_template():
    doc = Document(TEMPLATE)
    for element in list(doc.element.body):
        if element.tag != qn("w:sectPr"):
            doc.element.body.remove(element)
    doc.core_properties.title = "Envelope covers"
    section = doc.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)
    section.top_margin = section.bottom_margin = Mm(12)
    section.left_margin = section.right_margin = Mm(12)
    section.header_distance = section.footer_distance = Pt(0)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Calibri", Pt(11)
    normal.paragraph_format.space_before = normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.line_spacing = 1
    table = doc.add_table(rows=3, cols=3)
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for column, width in zip(table.columns, (91, 4, 91)):
        column.width = Mm(width)
    for row_index, row in enumerate(table.rows):
        row.height = Mm(4 if row_index == 1 else 124)
        row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for col_index, cell in enumerate(row.cells):
            cell.width = Mm(4 if col_index == 1 else 91)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            properties = cell._tc.get_or_add_tcPr()
            margins = OxmlElement("w:tcMar")
            borders = OxmlElement("w:tcBorders")
            label = row_index != 1 and col_index != 1
            for edge in ("top", "left", "bottom", "right"):
                margin = OxmlElement("w:" + edge)
                margin.set(qn("w:w"), "120" if label else "0")
                margin.set(qn("w:type"), "dxa")
                margins.append(margin)
                border = OxmlElement("w:" + edge)
                border.set(qn("w:val"), "single" if label else "nil")
                border.set(qn("w:sz"), "6")
                border.set(qn("w:color"), "000000")
                borders.append(border)
            properties.append(margins)
            properties.append(borders)
            if not label:
                cell.paragraphs[0].paragraph_format.line_spacing = Pt(1)
                cell.paragraphs[0].add_run().font.size = Pt(1)
    for column, heading in ((0, "ORIGINAL BID"), (2, "COPY OF BID")):
        cell = table.cell(0, column)
        paragraph(cell, heading, 14, True, 9)
        paragraph(cell, "{{ tender_title }}", 11, True, 6)
        paragraph(cell, "IFB NUMBER : {{ bid_reference }}", 11, True, 9)
        paragraph(cell, "DO NOT OPEN BEFORE\n{{ closing_date_short }} at {{ closing_time }}", 11, True, 9)
        paragraph(cell, "To:\n" + RECIPIENT, after=9)
        paragraph(cell, "From:\n" + SENDER, after=0)
    cell = table.cell(2, 0)
    paragraph(cell, "IFB Number:\n{{ bid_reference }}", 14, True, 14)
    paragraph(cell, "Closing Date:\n{{ closing_date_short }}", 14, True, 0)
    cell = table.cell(2, 2)
    paragraph(cell, RECIPIENT, 11, True, 12)
    paragraph(cell, "DO NOT OPEN BEFORE\n{{ closing_date_short }} at {{ closing_time }}", 11, True, 12)
    paragraph(cell, "From:\n" + SENDER, after=0)
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = Pt(1)
    p.add_run().font.size = Pt(1)
    output = io.BytesIO()
    doc.save(output)
    with zipfile.ZipFile(output) as source, zipfile.ZipFile(TEMPLATE, "w", zipfile.ZIP_DEFLATED) as target:
        for name in source.namelist():
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(entry, source.read(name))


if __name__ == "__main__":
    create_template()
