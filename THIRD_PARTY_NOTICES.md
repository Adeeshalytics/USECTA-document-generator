# Third-party software

USECTA Document Generator bundles Python and its application dependencies,
including Streamlit, docxtpl, python-docx, Jinja2, openpyxl, lxml, pandas,
NumPy, PyArrow and PyInstaller's bootloader. Their copyright and licence
files are retained within the installed package. A dependency inventory is
generated during the build as `third-party-inventory.json`.

PDF conversion uses the unmodified LibreOffice runtime from The Document
Foundation. Its licence and notices are included in the pdf-runtime directory.
LibreOffice is free software under the Mozilla Public License 2.0 and other
licences identified in its distribution. Source releases are available at
https://download.documentfoundation.org/libreoffice/src/ and the source code
repository at https://git.libreoffice.org/core.

The Windows installer is built with NSIS, the Nullsoft Scriptable Install
System: https://nsis.sourceforge.io/. Its licence and copyright notices apply
to the installer components and are retained in the bundled dependency notices.

USECTA's company templates and supplied catalogue are company assets; this
document does not grant permission to redistribute those assets publicly.
