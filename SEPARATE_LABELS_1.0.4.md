# Separate sample labels in USECTA 1.0.4

New Sample labels runs now give every label its own top, bottom, left and right
borders. Consecutive product rows do not share a border. Two copies per product
remain side by side, with a 12-point column gap and a small 5-point paragraph
gap between their separate row tables. Labels retain content-sized heights,
Calibri 14-point product names and 12-point IFB numbers.

Separate tables avoid unwanted continuation rules at page breaks. The blank
separator stays with the following label pair, and pairs cannot split between
sheets. Names are not shortened or reordered. Pages fill automatically; only
small gaps are added, rather than returning to the old three-product layout.

PDF checks with the private converter verified all four connected border
segments around every label, blank space between rows, exactly two copies of
each name/IFB, intact pairs, printable text bounds and no blank pages:

- 16 short Calcium Carbonate sample names produce 32 labels on one Letter sheet.
- 20 mixed-length names produce 40 labels over two sheets, with 13 and seven
  pairs respectively.
- Five long specifications with a long IFB produce ten labels on one sheet.
- 100 short names produce 200 labels over seven sheets: 16 pairs on each of
  the six full sheets, then four pairs on the last.

Capacity varies with name and IFB lengths. Longer text expands its label; the
last sheet can have unused space. Print at Actual size / 100% on Letter paper,
and test on plain paper before using full sticker paper. This is not calibrated
to an unspecified pre-cut sheet.

Layout versions 1 and 2 remain available for exact regeneration of old saved
runs; both reproduced previously installed output byte-for-byte. Generate a
new run to get separate labels. Existing saved files are not overwritten.
Source regressions check independent borders, 100 separate row tables, small
borderless separators, expanding text, input validation, UI generation,
catalogue loading, draft navigation, history and PDF failure recovery.

The final source suite passed 73 tests; two legacy PDF-text checks skipped.
All 11 rendered pages were visually reviewed. The clean packaged application
passed Word/PDF, backup/import, network protection and lifecycle checks. Its
label DOCX matched final source bytes, and its PDF passed the same independent
four-border geometry check.

The 1.0.4 installer successfully updated the existing user installation. The
installed PDF passed the same border check; document generation, backup/import
and lifecycle checks passed. All 37 protected company files remained unchanged.
Artifact hash and results are in release/ACCEPTANCE_REPORT-1.0.4.json.

The build remains unsigned. Clean offline staff-PC acceptance and company
template review are still required before company-wide production approval.
