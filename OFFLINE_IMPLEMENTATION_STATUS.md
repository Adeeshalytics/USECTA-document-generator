# USECTA offline edition — implementation status

## What the system is

A template-based business document generator, not an AI writing service. It
fills USECTA's Word templates using tender items and supplier details, and has
a separate quotation workflow. The supplied assets include six tender templates,
a quotation starter, and the SPMC/03/2026 50-item catalogue.

## Gaps addressed

| Original gap | Offline implementation |
| --- | --- |
| Python/terminal setup required for users | Bundled Python runtime, Windows setup executable and desktop/Start-menu shortcuts |
| Optional cloud configuration and remote storage | Packaged edition always uses local storage and ignores cloud credentials |
| Data tied to the source folder | Per-Windows-user workspace, separate from installation; retained on update/uninstall |
| All screens executed on each interaction | Only the selected screen runs; templates and history are loaded on demand |
| Repeated template parsing and per-document converter startup | Cached template parsing, one template read per batch and batched PDF conversion |
| Database connections remained open | Explicit commit/rollback/close and serialized local workspace operations |
| No controlled desktop lifecycle | Localhost-only server, duplicate-launch protection, health checks, Exit application and rotating logs |
| No recoverable data-transfer workflow | Full backup/restore, daily startup backup and share packages with keep/replace controls |
| Template replacement could change historical output | Immutable template versions and saved input snapshots |
| PDF failure could lose usable output | DOCX saved even if optional PDF conversion fails |

The local record file uses embedded SQLite. This is a file inside the workspace,
not an external database server: no login, database installation or internet
connection is required. Each staff computer is independent, not synchronized.

## Checks completed

- The 1.0.4 source separates every new label into its own four-border box,
  with small gaps between rows and columns. 73 source tests passed; two legacy
  PDF-text checks skipped. Eleven rendered pages were visually reviewed.
  PDF geometry checks verified four connected, independent borders per label,
  gaps, no blank pages, complete IFB/name pairs and no clipped text. The
  100-product run contains all 200 labels on seven sheets; 16 short products
  fit 32 labels on one sheet. Layouts 1 and 2 still reproduce old saved output
  byte-for-byte. See SEPARATE_LABELS_1.0.4.md for the current layout.

- The 1.0.4 installer updated the existing installation successfully. Installed
  Word/PDF output matched the final source, and the installed PDF passed the
  independent four-border geometry check. Backup/import and lifecycle checks
  passed; all 37 protected company files retained their original hashes.
  Current evidence is in release/ACCEPTANCE_REPORT-1.0.4.json. The supplied icon
  remains verified in the executables and shortcuts. Production caveats below
  still apply.

- The 1.0.3 source adds dense, variable-height sample labels, automatic page
  filling and backward-compatible regeneration of layout-1 saved runs.
  72 source tests passed; two legacy PDF-text checks skipped. Ten rendered
  pages were visually reviewed. Separate PDF checks verified all 200 labels
  from a 100-product run, intact pairs, IFB numbers, printable bounds and no
  blank pages. Eighteen short products fit 36 labels on one Letter sheet.
  See COMPACT_LABELS_1.0.3.md for measured capacity and print constraints.

- The 1.0.3 installer updated the existing installation successfully. Installed
  Word/PDF, backup/import and lifecycle checks passed. All 33 protected company
  database, template and export files retained their exact hashes. Label output
  matched final source bytes; executable, installer and shortcut icons passed.
  Historical evidence is in release/ACCEPTANCE_REPORT-1.0.3.json. The unsigned build
  still requires the production acceptance checks below.

- Release 1.0.2 adds editable Sample labels recreated from the supplied PDF,
  with two copies per product, catalogue loading, Word/PDF downloads and saved
  regeneration. The complete source suite passed 70 tests; two legacy PDF-text
  checks skipped. Five rendered pages were visually checked, including long
  names and multi-page output; the real packaged interface generated Word/PDF.
- The 1.0.2 installer updated the existing user installation successfully.
  Installed label output matched final source output byte-for-byte. DOCX/PDF,
  backup/import, offline-network protection and lifecycle checks passed;
  existing database, template and export hashes were unchanged. The supplied
  icon was verified in the installer/executable and both shortcuts.
  Historical evidence is in release/ACCEPTANCE_REPORT-1.0.2.json. See
  SAMPLE_LABELS_1.0.2.md for printing guidance and layout limitations.
- Installed 1.0.2 measurements on this computer: launch 3.633 seconds cold /
  1.812 seconds on restart, ten tender DOCX files 0.706 seconds and ten tender
  PDFs 44.713 seconds. Clean staff-PC performance remains unverified.

- Maintenance release 1.0.1 corrects the reported date-saving interface and
  missing-field guidance, adds editor shortcuts and the supplied application
  icon. Its combined source suite passed 58 tests; two PDF-text tests skipped.
  See FIXES_1.0.1.md for the exact fixes and verification scope.
- The 1.0.1 installer successfully updated the existing user installation.
  Installed DOCX/PDF, backup/import and lifecycle checks passed; the existing
  database and template hashes were unchanged. The reported date issue was
  also verified through the packaged interface in an isolated workspace.
  Historical evidence is in release/ACCEPTANCE_REPORT-1.0.1.json; the older
  release/ACCEPTANCE_REPORT.json below describes the original 1.0.0 acceptance.

- 46 source tests passed; one legacy PDF-text extraction test skipped because
  `pdftotext` is unavailable. A separate real converter smoke check passed.
- Before the GitHub push, the combined suite including the repository's existing
  desktop/USB tests passed: 50 passed, two PDF-text tests skipped (`pdftotext`
  unavailable). Existing desktop files and cloud workflows were preserved;
  USB snapshot connections now close explicitly before Windows folder moves.
- Smoke checks generated 10 tender DOCX files and one quotation across all seven
  templates, converted all 10 tender files to PDF, restored and regenerated an
  exact saved run, imported company records and rejected an external connection.
- Latest source-run measurements on this Windows 11 computer: initialization
  1.049 seconds, 10 DOCX files 0.987 seconds, 10 PDFs 33.820 seconds. These are
  measurements, not performance guarantees for other company computers.
- Rendered every page of the sample PDFs. Text extraction found no unresolved
  placeholders. Logos and letterhead remain present in inspected samples.
- The built installer passed install, same-version reinstall, shortcuts and
  quoted uninstaller registration checks. Its installed executable passed all
  smoke/lifecycle checks with only System32 on PATH. Uninstall removed the
  application files, shortcuts and registry entries while retaining test data.
  See release/ACCEPTANCE_REPORT.json for the exact artifact and results.
- Installed-build timings: launch 4.374 seconds cold / 2.020 seconds on restart,
  10 DOCX files 1.018 seconds and 10 PDFs 39.136 seconds. These were measured on
  the development computer, not a clean staff PC.
- The packaged interface generated and saved a sample quotation with a verified
  USD 20.00 total. Backup/sharing and quotation screens loaded successfully;
  Exit application stopped its server. Windows duplicate-launch and authorized
  stop handling are also covered by a source regression test.

## Remaining production acceptance

1. Test the exact installer on a clean, offline Windows 10/11 x64 standard-user
   account without Python, Office or LibreOffice. This development computer is
   not a substitute for that test.
2. Sign the release using the company's code-signing certificate if trusted
   publisher installation is required. This build is unsigned.
3. Company approval of template content and pagination. Existing collection/
   cover footer wording and agreement page-count text remain as supplied.
   The sample agency agreement produced seven pages; the first-page footer
   still stated "1 of 5". One long item description pushed the final Bid Form
   authorization line onto a second page. Do not submit samples as final bids.
4. Confirm SPMC/03/2026's bid acceptance validity date. It is intentionally not
   inferred from the closing date; Bid Form generation requires it.
5. Confirm internal handling of signatures, supplier records and backups.
   Backups are unencrypted and should only be shared with trusted staff.

PDF generation is optional and substantially slower than Word generation.
The current implementation prioritizes fast local DOCX generation; PDF timing
must be measured on the slowest intended company machine before promising it.

Use OFFLINE_USER_GUIDE.md for staff instructions and RELEASE_CHECKLIST.md for
the final acceptance process. Do not describe an unsigned, untested clean-PC
build as fully production-approved.
