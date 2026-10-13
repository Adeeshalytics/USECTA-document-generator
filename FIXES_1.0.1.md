# USECTA Document Generator 1.0.1

## Reported problems addressed

- Removed the validity-enable checkbox. Unknown dates are genuinely blank;
  an entered validity date is saved directly and the confirmation displays it.
  No date is inferred from the closing date. Explicit clearing remains possible.
- Replaced internal placeholder IDs in tender/quotation validation with readable
  field labels and instructions identifying the relevant screen.
- Consolidated prerequisites across selected tender documents. Missing items,
  supplier details and validity dates can be corrected together. No partial
  document set is silently generated when selected templates are incomplete.
- Added direct Edit tender dates and Edit selected supplier navigation while
  preserving the tender, template and item selection.
- Added the supplied USECTA artwork to the sidebar and favicon, Windows executable,
  installer/uninstaller and legacy desktop shortcuts. Assets accompany USB copies.

## Verification

Eight new isolated regression tests passed, covering direct date save/restart,
blank and cleared dates, invalid-date rollback, consolidated missing-field
guidance, real generation of all six tender templates, envelope-only generation,
navigation state and multi-resolution icon packaging.
The complete source suite passed: 58 passed, two PDF-text extraction tests skipped
because `pdftotext` is unavailable. The packaged converter is tested separately.

The rebuilt installer updated the user's existing installation successfully.
Installed checks generated 10 tender Word files and one quotation, converted
the tender files to PDF, restored a backup, transferred company records,
blocked external network connections, and verified duplicate launch/restart/stop.
All eight protected existing database/template files retained identical hashes.
All seven embedded icon frames in the app and installer match the supplied ICO.
The existing desktop and Start-menu shortcuts explicitly reference the supplied
ICO to avoid retaining a cached older executable icon after the update.
The real packaged interface saved the entered date correctly in a test workspace.
See `release/ACCEPTANCE_REPORT-1.0.1.json` for the artifact checksum and results.

See release acceptance evidence for packaged tests. An installer update does not
repair previously discarded dates: enter the confirmed validity date and save
again. Missing supplier details must be supplied by the company, not invented.

This maintenance update does not change company templates, legal text or recorded
business data. Company template approval, clean-offline-PC acceptance and code
signing remain required before company-wide production approval.
