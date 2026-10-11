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
