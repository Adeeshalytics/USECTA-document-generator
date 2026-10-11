# Offline Windows release acceptance

Record machine/Windows details, installer SHA256, version and timings. Do not
label a release production-ready solely because source tests pass.

- Install under a standard, non-administrator Windows account with no Python,
  Office or LibreOffice installed and internet disconnected.
- Launch from desktop and Start menu. Verify the interface uses localhost only.
- Launch a second time: one server remains active and the existing page opens.
- Generate all six tender templates and an independent quotation. Verify required
  fields are enforced, per-item counts, quotation arithmetic and output location.
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
