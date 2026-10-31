"""Arrange wide envelope labels and a small IFB label on landscape A4."""
import io
from pathlib import Path
import zipfile

from docx import Document
from docx.enum.section import WD_ORIENT
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


def paragraph(cell, text, size=11, bold=False, after=4):
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


def style_cell(cell, bordered):
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    properties = cell._tc.get_or_add_tcPr()
    margins, borders = OxmlElement("w:tcMar"), OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        margin = OxmlElement("w:" + edge)
        margin.set(qn("w:w"), "100" if bordered else "0")
        margin.set(qn("w:type"), "dxa")
        margins.append(margin)
        border = OxmlElement("w:" + edge)
        border.set(qn("w:val"), "single" if bordered else "nil")
        border.set(qn("w:sz"), "6")
        border.set(qn("w:color"), "000000")
        borders.append(border)
    properties.append(margins)
    properties.append(borders)


def create_template():
    doc = Document(TEMPLATE)
    for element in list(doc.element.body):
        if element.tag != qn("w:sectPr"):
            doc.element.body.remove(element)
    doc.core_properties.title = "Envelope covers"
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = Mm(297), Mm(210)
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
    for column, width in zip(table.columns, (128, 17, 128)):
        column.width = Mm(width)
    for row_index, row in enumerate(table.rows):
        row.height = Mm((86, 8, 82)[row_index])
        row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for col_index, cell in enumerate(row.cells):
            cell.width = Mm(17 if col_index == 1 else 128)
            label = (row_index, col_index) in ((0, 0), (0, 2), (2, 0))
            style_cell(cell, label)
            if not label:
                cell.paragraphs[0].paragraph_format.line_spacing = Pt(1)
                cell.paragraphs[0].add_run().font.size = Pt(1)
    for column, heading in ((0, "ORIGINAL BID"), (2, "COPY OF BID")):
        cell = table.cell(0, column)
        paragraph(cell, heading, 14, True, 6)
        paragraph(cell, "{{ tender_title }}", 11, True, 4)
        paragraph(cell, "IFB NUMBER : {{ bid_reference }}", 11, True, 4)
        paragraph(cell, "DO NOT OPEN BEFORE\n{{ closing_date_short }} at {{ closing_time }}", 11, True, 5)
        paragraph(cell, "To:\n" + RECIPIENT, after=5)
        paragraph(cell, "From:\n" + SENDER, after=0)
    cell = table.cell(2, 0)
    paragraph(cell, RECIPIENT, 12, True, 10)
    paragraph(cell, "DO NOT OPEN BEFORE\n{{ closing_date_short }} at {{ closing_time }}", 11, True, 10)
    paragraph(cell, "From:\n" + SENDER, after=0)
    # A small, independent label centered in the lower-right space, as sketched.
    holder = table.cell(2, 2)
    small = holder.add_table(rows=1, cols=1)
    small.autofit = False
    small.alignment = WD_TABLE_ALIGNMENT.CENTER
    small.columns[0].width = small.cell(0, 0).width = Mm(96)
    small.rows[0].height, small.rows[0].height_rule = Mm(32), WD_ROW_HEIGHT_RULE.AT_LEAST
    small.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
    cell = small.cell(0, 0)
    style_cell(cell, True)
    paragraph(cell, "IFB Number: {{ bid_reference }}", 12, True, 5)
    paragraph(cell, "Closing Date: {{ closing_date_short }}", 12, True, 0)
    for p in holder.paragraphs:
        p.paragraph_format.line_spacing = Pt(1)
        p.paragraph_format.space_after = p.paragraph_format.space_before = Pt(0)
        for run in p.runs:
            run.font.size = Pt(1)
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
