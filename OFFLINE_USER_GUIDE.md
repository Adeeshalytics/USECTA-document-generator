# USECTA Document Generator — offline edition

## Install from a pendrive

Copy USECTA-Document-Generator-Setup-1.0.4.exe to the computer and run it.
Windows 10/11, 64-bit is required. No Python, internet, Office, or database
server is required. The PDF converter is included. Install while USECTA is
closed. Open USECTA Document Generator using the desktop or Start-menu shortcut.

The interface opens in your default browser at a 127.0.0.1 address. This is
your own computer. Keep the browser open while using the application. To stop
the application, click Exit application in the sidebar. Closing just the tab
leaves the local application available; the shortcut reopens it.

## Where your work is saved

Records, suppliers, tenders, catalogues, templates and generated documents are
stored in `%LOCALAPPDATA%\USECTA Document Generator` for your Windows account.
Open Backup & sharing and click Open workspace folder to find them. Each
computer has an independent workspace. There is no automatic synchronisation.
The program installation is separate from your records. Updating or uninstalling
the program preserves the workspace.

## Generate documents

1. Add or edit suppliers in Suppliers.
2. Set tender dates and catalogue rows in Tenders & items.
3. In Tender documents, select a tender, document templates, item numbers and
   the supplier for those items. Generate separately for different suppliers.
4. Generate documents, review the wording and pagination, then download them or
   open the saved output folder. PDF conversion is optional; DOCX remains
   available if PDF conversion fails.

SPMC/03/2026 and the supplied 50-item catalogue are included. Enter its confirmed
bid acceptance validity date before generating Bid Forms. Never assume that
date equals the closing date. Company letterhead, signatures, fixed recipient
details and legal text come from the templates; review them before submission.
The original collection/cover footer wording and typed agreement page counts
remain as supplied. Edit the relevant Word template and import a new version
if those should change.

The validity field starts blank when unknown. Every date you enter is saved
when you click Save tender; no enable checkbox is required. Clear the field
and save only if you intend to remove the validity date. The saved-date
confirmation states whether a date was recorded.

For Agency Agreements, select the relevant item numbers and a supplier with
its Registration number, country and registered address filled in. The item
names are taken automatically from the selected catalogue rows. Use Edit tender
dates or Edit selected supplier to jump directly to the relevant editor.
Generation is disabled until all selected documents' required data is complete.

Use Quotations for independent products, units, prices and terms. This workflow
does not use tender catalogue fees. No automatic taxes or currency conversion
are applied.

## Sample labels

Open Sample labels in the sidebar. Enter the IFB number and one product name
per line, or choose a tender and item numbers and click Load selected items into
labels. Edit the exact specifications before generating; this does not edit the
saved catalogue. Each product receives two identical bordered labels. Compact
rows fit their text and automatically fill the available sheet height, without
large gaps or three-product page breaks. Product text is 14 point and IFB text
12 point; long names wrap and grow their row without clipping. Every label has
its own four borders, with a small blank gap between rows and between columns.
Label size is not fixed; pre-cut sheets need calibration.

Word labels are editable; PDF is recommended for printing. Print on Letter
paper (8.5 by 11 inches) at Actual size / 100%, not Fit to page. Test first on
plain paper before using sticker stock. Do not assume this layout aligns with
an unspecified pre-cut sticker sheet. Saved label runs can be regenerated using
their original product names, IFB number and layout. Older saved runs retain
their original layout; generate a new run to get separated labels. No supplier or bid validity date
is required for labels. Optional PDF failure does not discard Word output.

## Backup, restore and company sharing

In Backup & sharing, choose Complete workspace backup, Prepare package, then
Download package. Save it onto a separate pendrive or backup location. A backup
includes records and template versions; generated files can be regenerated
from saved runs and are not duplicated in the package. Logs and other backup
archives are also excluded. Backups are unencrypted; store them securely.

To restore, upload a USECTA backup, review the counts, tick the replacement
confirmation and click Restore workspace. A safety backup of the current
workspace is kept under its backups folder before replacement. Restored data
becomes the active workspace; previous exported output files remain on disk.

For colleagues, choose Company records to share. This package contains suppliers,
tenders, catalogues and templates but excludes document-run history. Import it
using Import company records. Existing suppliers and tenders are kept unless
you explicitly choose replacement. Templates are imported as separate versions.
A safety backup is made first. Share packages are intended for trusted company
members because the Word templates may contain fixed signatures and details.

An automatic backup is also created once per day on application startup when a
workspace already contains templates. Backups remain local until you copy them
elsewhere; local backups do not protect against losing the computer.

## Troubleshooting

If opening the shortcut twice, USECTA reuses the running instance. If a startup
error appears, inspect the logs folder inside the workspace. For technical
support, share the relevant log after removing any sensitive details. The
installer is currently unsigned, so Windows may display an unknown-publisher
warning. Verify that your installer came from your company administrator.

PDF wrapping can differ from Microsoft Word when fonts differ. Review PDFs
before sending. The app preserves template formatting and does not shrink text
to force a particular page count.
