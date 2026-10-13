# Sample labels in USECTA 1.0.2

The Sample labels screen recreates the supplied bordered printout as editable
Word text, with optional PDF copies. Each product appears twice, side by side.
IFB number and exact product names are editable. Catalogue names can be loaded
without altering the catalogue. Labels do not require supplier or validity data.

The reference is Letter size, not A4. The two columns have 243-point nominal
label widths, with reference-style row heights and whitespace. Minor uneven
horizontal/vertical offsets between the original manually positioned boxes are
aligned consistently in the new layout. Borders and centered Calibri text are
retained. Longer names wrap and boxes expand rather than clipping. This is not
a calibrated layout for an unspecified brand of pre-cut sticker stock.

Print PDF at Actual size / 100% on Letter paper and test on plain paper first.
If the printer only supports A4 or pre-cut label sheets, confirm the stock
dimensions before relying on exact physical alignment.

Saved label runs preserve their IFB number, product names and layout version;
regeneration is deterministic. Word files survive an optional PDF failure.
Draft names survive navigation and changed inputs hide stale downloads.

Twelve isolated regression tests cover editable paired labels, input validation,
safe filenames/XML, saved-run regeneration, catalogue loading, draft navigation,
unchanged catalogue data and PDF failure recovery. The complete suite passed
70 tests with two PDF-text checks skipped. Canonical document rendering and
visual review covered a reference reconstruction, changed fields and seven
products spanning three pages, including a long description. Packaged output
must match the final source label document byte-for-byte before release.

The final packaged and installed outputs passed that byte-for-byte comparison.
The 1.0.2 installer updated the existing installation; all protected company
records, templates and exports remained unchanged. Real interface generation,
installed Word/PDF conversion, backup/import and restart checks passed. See
release/ACCEPTANCE_REPORT-1.0.2.json for the artifact hash and verification scope.
The build is unsigned; clean offline staff-PC acceptance remains pending.
