# Compact sample labels in USECTA 1.0.3

New label runs use a continuous two-column layout instead of the original
three-product pages. Large blank gaps and fixed label heights are removed.
Each product still has two identical copies side by side. Rows fit their text,
share horizontal cut lines and flow automatically to the next sheet without
splitting a pair. Product text is Calibri 14 point; IFB text is 12 point.
Letter pages use 24-point margins and a 12-point gap between the two columns.
Long specifications wrap and expand, rather than being shortened or clipped.

Rendered PDF checks with the private bundled converter confirmed:

- 18 short-name products produce 36 labels on one sheet.
- 20 mixed-length products produce 40 labels on two sheets, with 14 and six
  product pairs respectively.
- Five long specifications with an almost maximum-length IFB fit on one sheet.
- 100 short-name products produce 200 labels across six sheets, with 18 pairs
  on each full sheet and ten on the last sheet.

These are measured examples, not a fixed capacity for every product name.
The last sheet may have unused space and remaining space may be too small for
the next complete pair. Names and item order are retained. All text remains
editable in Word; PDF is recommended for predictable printing.

Saved layout-1 runs retain their original spaced format. The compatibility
check reproduced a previously installed label document byte-for-byte. Generate
a new run to use the compact format. Label regression tests cover automatic
row sizing, all 100 pairs, input handling, UI drafts, catalogue loading,
historical regeneration and optional PDF failure. The complete suite passed
72 tests with two legacy PDF-text tests skipped; separate real PDF conversion
and text/page/bounds checks passed.

Print at Actual size / 100% on Letter paper; test on plain paper first. This
variable-height format is intended for full sticker paper, not an unspecified
pre-cut label sheet. Confirm the printer supports the margins. The installer
remains unsigned; clean offline staff-PC acceptance is still required.

The final 1.0.3 installer successfully updated the existing user installation.
Installed label output matched the final source byte-for-byte; Word/PDF,
backup/import and lifecycle checks passed. All 33 protected company files
remained unchanged. Artifact hash and results are recorded in
release/ACCEPTANCE_REPORT-1.0.3.json.
