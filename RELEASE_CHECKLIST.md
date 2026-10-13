# Offline Windows release acceptance

Record machine/Windows details, installer SHA256, version and timings. Do not
label a release production-ready solely because source tests pass.

- Install under a standard, non-administrator Windows account with no Python,
  Office or LibreOffice installed and internet disconnected.
- Launch from desktop and Start menu. Verify the interface uses localhost only.
- Launch a second time: one server remains active and the existing page opens.
- Generate all six tender templates and an independent quotation. Verify required
  fields are enforced, per-item counts, quotation arithmetic and output location.
- Enter and save a bid validity date without any enable checkbox; verify it
  survives restart. Clear it explicitly, then confirm Bid Form is blocked but
  envelopes still work. Reject a date before closing without altering saved data.
- Confirm missing supplier/item/date guidance is consolidated and uses readable
  labels. Complete the details and verify all selected templates generate.
- Verify the supplied icon on the executable, setup/uninstaller, desktop and
  Start-menu shortcuts, and in the application sidebar/browser favicon.
- Generate Sample labels manually and from catalogue selections. Edit names
  and IFB number without changing catalogue data; verify two copies per product.
  Check Letter page size, Actual size / 100% print instructions, long-name
  wrapping, multiple pages, saved-run regeneration and PDF failure recovery.
  Generate 16 short products and 100 products; verify dense automatic page
  filling, exactly two copies, no split pairs, missing labels or blank pages.
  Verify every label has four borders with blank gaps between rows/columns.
  Regenerate layout-1 and layout-2 runs and confirm their old layouts are retained.
- Render PDF copies using the bundled runtime; review all six document types,
  logos, fonts, headers/footers, signatures and long-name/50-item pagination.
- Enter quotation and tender drafts, navigate between screens, and verify values
  remain. Edit catalogue rows and supplier details, then restart and confirm saves.
- Create a backup; restore into a separate workspace and regenerate a saved run.
- Import company records twice: no duplicate templates on the second import.
  Verify keep-existing and explicit replace behavior without replacing history.
- Reject malformed, unexpected-member, oversized and checksum-invalid archives
  before changing live records.
- Exit application, confirm child process and localhost listeners stop, relaunch.
- Install an update over the existing installation. Preserve records, uploads,
  old template versions and regeneration behavior.
- Uninstall. Preserve user workspace and remove application files/shortcuts.
- Reinstall and verify existing records are available.
- Record cold/warm launch, normal interaction, 10 DOCX and 10 PDF timings on the
  slowest supported company computer. PDF conversion is measured separately.
- Document unsigned-installer status and any remaining font substitutions or
  business template corrections before distribution.
