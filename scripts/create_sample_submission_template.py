"""Create the sample cover letter using existing USECTA letterhead artwork."""
from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]


def floating_picture(paragraph, path, x, y, width, behind=False):
    shape = paragraph.add_run().add_picture(str(path), width=Pt(width))
    inline = shape._inline
    anchor = OxmlElement("wp:anchor")
    for name, value in {"distT": "0", "distB": "0", "distL": "0", "distR": "0", "simplePos": "0",
                        "relativeHeight": "0" if behind else "2", "behindDoc": "1" if behind else "0",
                        "locked": "0", "layoutInCell": "1", "allowOverlap": "1"}.items():
        anchor.set(name, value)
    simple = OxmlElement("wp:simplePos"); simple.set("x", "0"); simple.set("y", "0"); anchor.append(simple)
    for axis, value in [("H", x), ("V", y)]:
        position = OxmlElement("wp:position" + axis); position.set("relativeFrom", "page")
        offset = OxmlElement("wp:posOffset"); offset.text = str(round(value * 12700))
        position.append(offset); anchor.append(position)
    anchor.append(deepcopy(inline.find(qn("wp:extent"))))
    anchor.append(OxmlElement("wp:wrapNone"))
    for tag in ("wp:docPr", "wp:cNvGraphicFramePr", "a:graphic"):
        anchor.append(deepcopy(inline.find(qn(tag))))
    inline.getparent().replace(inline, anchor)


def create_template():
    original = ROOT / "company_templates" / "Cover letter.docx"
    doc = Document(original)
    # Keep the existing letterhead's sidebars and watermark. Rebuild only the body.
    body = doc._element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Calibri", Pt(11)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal.paragraph_format.space_after = Pt(8)
    normal.paragraph_format.line_spacing = 1.08
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for style in doc.styles:
        for border in style.element.findall(".//" + qn("w:pBdr")):
            border.getparent().remove(border)
    section = doc.sections[0]
    section.different_first_page_header_footer = False
    section.page_width, section.page_height = Pt(595), Pt(842)
    section.left_margin, section.right_margin = Pt(93), Pt(25)
    section.top_margin, section.bottom_margin = Pt(210), Pt(48)
    section.header_distance = Pt(36)
    # Keep the existing vector sidebars, replacing the old watermark with the
    # exact embedded letterhead/watermark artwork from the supplied sample PDF.
    for shape in section.header._element.xpath('.//*[local-name()="shape"]'):
        if shape.xpath('.//*[local-name()="imagedata"]'):
            shape.getparent().remove(shape)
    for p in section.header.paragraphs:
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = Pt(1)
        for run in p.runs:
            run.font.size = Pt(1)
    p = section.header.paragraphs[0]
    floating_picture(p, ROOT / "assets/sample-submission-letterhead.png", 81.75, 57.95, 489.5)
    floating_picture(p, ROOT / "assets/sample-submission-watermark.png", 119.5, 317.76, 379.7, behind=True)
    footer = section.footer
    for child in list(footer._element):
        footer._element.remove(child)
    footer.add_paragraph()
    doc.core_properties.title = "Sample submission cover letter"
    doc.core_properties.author = "USECTA (Pvt) Ltd"

    p = doc.add_paragraph("{{ recipient_name }}\t{{ document_date }}")
    p.paragraph_format.tab_stops.add_tab_stop(Pt(477), WD_TAB_ALIGNMENT.RIGHT)
    p.paragraph_format.space_after = Pt(0)
    doc.add_paragraph("{{ recipient_address }}").paragraph_format.space_after = Pt(20)
    doc.add_paragraph("{{ salutation }}").paragraph_format.space_after = Pt(14)
    p = doc.add_paragraph("Submission of Samples - Tender No. {{ bid_reference }}", "Title")
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before, p.paragraph_format.space_after = Pt(0), Pt(14)
    p.paragraph_format.keep_with_next = True
    for run in p.runs:
        run.bold = True
        run.font.name, run.font.size = "Calibri", Pt(11)
        run.font.color.rgb = RGBColor(0, 0, 0)
    doc.add_paragraph("We hereby submit the required samples for the above-mentioned tender {{ tender_item_word }} as per the bid specifications:")
    doc.add_paragraph("Items:").paragraph_format.space_after = Pt(2)
    doc.add_paragraph("{%p for item in sample_items %}")
    p = doc.add_paragraph("{{ loop.index }}.   {{ item.description }} - No. {{ item.item_number }}")
    p.paragraph_format.left_indent = Pt(18)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_together = True
    for run in p.runs:
        run.bold = True
    doc.add_paragraph("{%p endfor %}")
    doc.add_paragraph("Quantity: {{ quantity_sentence }}")
    doc.add_paragraph("IFB Number: {{ bid_reference }}").paragraph_format.space_after = Pt(20)
    doc.add_paragraph("{%p if coa_enclosed %}")
    doc.add_paragraph("{{ coa_paragraph }}")
    doc.add_paragraph("{%p endif %}")
    doc.add_paragraph("These samples are submitted for evaluation purposes only and are not intended for commercial use or resale. Please feel free to contact us should you require any additional clarification or documents.")
    doc.add_paragraph("Thank you for your attention.")
    p = doc.add_paragraph("Yours faithfully,")
    p.paragraph_format.space_after = Pt(30)
    p.paragraph_format.keep_with_next = True
    p = doc.add_paragraph("{{ signatory_name }}\n{{ signatory_designation }}")
    p.paragraph_format.keep_together = True
    target = ROOT / "assets" / "Sample submission cover letter.docx"
    doc.save(target)
    print(target)


if __name__ == "__main__":
    create_template()
