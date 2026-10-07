# USECTA template check report

All six templates parsed and rendered after the corrections listed below. Originals remain preserved under data/review/originals in the cloud workspace. The downloadable company_templates folder contains the corrected copies.

## Corrections (text only)

### Bid Document.docx

- '{ document_date }}' → '{{ document_date }}' (1 occurrence(s)).

### AGENCY AGREEMENT.docx

- '{{ supplier_name }}a company' → '{{ supplier_name }}, a company' (1 occurrence(s)).
- 'Document{{ bid_reference }}' → 'Document {{ bid_reference }}' (1 occurrence(s)).
- '{{ bid_reference }}and any' → '{{ bid_reference }} and any' (1 occurrence(s)).

### Cover letter.docx

- '{{ bid_reference }}–' → '{{ bid_reference }} –' (1 occurrence(s)).

### Bid Form.docx

- '{{ item_number }}IFB' → '{{ item_number }}  IFB' (1 occurrence(s)).

### Envelop covers.docx

- '10.00 a.m.' → '{{ closing_time }}' (3 occurrence(s)).
- 'PROCUREMENT OF PHARMACEUTICAL RAW MATERIALS' → '{{ tender_title }}' (2 occurrence(s)).

### Authorised Personnal.docx

No placeholder corrections needed.

## Verified output

- 12 sample DOCX files and 12 PDFs generated, including three selected items and complete 50-item collection/personnel lists.
- Word style, numbering, settings, theme, and image parts remained unchanged. Section/page settings, table widths, and repeated cell properties passed structural checks.
- Collection and personnel letter PDF previews were visually checked for letterhead, watermarks, table/list content, and signatures.
- A sample long item name made one bid form span two pages. The 50-item collection/personnel samples spanned three pages. The app preserves formatting instead of shrinking text or margins to force one-page output.

## Template details retained for your review

- Collection/cover letter footer text still says Agency Agreement. It was not automatically redesigned.
- Agency agreement contains typed page counts. Use Word PAGE/NUMPAGES fields if automatic page numbering is wanted.
- Authorized person details and signatures remain fixed as supplied. Edit the template if those should change.
- SPMC recipient details and legal clauses remain fixed as supplied.

## Confirmed live tender information

- SPMC/03/2026; closing 3 November 2026 at 10:00 a.m.; 50 supplied catalogue items with quantities and separate document fees.
- Bid acceptance validity date remains unconfirmed. Enter it in Tenders & items before generating the Bid Form.

Sample documents use fictitious reference/dates/supplier data and are not for submission.

## Collection table width update

Following the user's requested adjustment, the collection table now allocates 12% of its width to Item No, 68% to Item, and 20% to Document Fee. Its total width remains 9900 twips. Fixed table layout keeps these proportions, and the inherited right paragraph indent is cleared within the table so the narrow columns use their available space. Fonts, borders, branding, margins, and other documents remain unchanged.

The revised template was rendered with item numbers 32, 36, 41, 46, 48, 21, 25, and 50 and checked visually in PDF. The longer descriptions have more room and the Item No header fits on one line. Existing saved templates and runs retain their previous version.
